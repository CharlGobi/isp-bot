"""
ISP API Server - isp_api.py
Lightweight Flask REST bridge between MT5 and the ISP Command Center dashboard.

Runs on http://localhost:5051
Serves ISP_CommandCenter.html at GET /

All endpoints return {"ok": bool, "data": {...}, "ts": "ISO8601"}
Never returns a 500 — errors are surfaced in the ok/error fields.

Start: python isp_api.py
Or let isp_launcher.py start it automatically.
"""

import json
import logging
import os
import queue
import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────
load_dotenv()

MT5_LOGIN    = int(os.getenv("MT5_LOGIN",    "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD",     "")
MT5_SERVER   = os.getenv("MT5_SERVER",       "Exness-MT5Trial9")
API_PORT     = int(os.getenv("API_PORT",     "5051"))
SENTIMENT_PORT = int(os.getenv("SENTIMENT_PORT", "5050"))
DAILY_DD_LIMIT = float(os.getenv("DAILY_DD_LIMIT", "3.0"))
MAX_DD_LIMIT   = float(os.getenv("MAX_DD_LIMIT",   "8.0"))
CHALLENGE_START_BALANCE = float(os.getenv("CHALLENGE_START_BALANCE", "10000"))

MAGIC_MAP = {
    "EURUSD": int(os.getenv("MAGIC_EURUSD", "202601")),
    "GBPUSD": int(os.getenv("MAGIC_GBPUSD", "202602")),
    "USDJPY": int(os.getenv("MAGIC_USDJPY", "202603")),
    "XAUUSD": int(os.getenv("MAGIC_XAUUSD", "202604")),
}
ISP_MAGICS = set(MAGIC_MAP.values())

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "isp_api.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("ISP.API")

# ── MT5 availability ──────────────────────────────────────────
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    log.warning("MetaTrader5 library not found — running in offline/CSV-only mode")

# ── MT5 thread-safe queue ─────────────────────────────────────
# MT5 Python library requires all calls from the SAME thread that
# called mt5.initialize(). Flask uses multiple threads, so we marshal
# all MT5 calls through a single worker thread via a queue.
_mt5_queue   = queue.Queue()
_mt5_results = {}
_mt5_lock    = threading.Lock()
_mt5_connected = False

def _mt5_worker():
    """Single thread that owns the MT5 connection."""
    global _mt5_connected
    if not MT5_AVAILABLE:
        return
    try:
        ok = mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        _mt5_connected = ok
        if ok:
            log.info(f"MT5 connected: {mt5.terminal_info().name} | account {MT5_LOGIN}")
        else:
            log.warning(f"MT5 initialize failed: {mt5.last_error()}")
    except Exception as e:
        log.error(f"MT5 init error: {e}")
        _mt5_connected = False

    while True:
        try:
            req_id, fn = _mt5_queue.get(timeout=1.0)
            try:
                result = fn(mt5)
                with _mt5_lock:
                    _mt5_results[req_id] = {"ok": True, "data": result}
            except Exception as e:
                with _mt5_lock:
                    _mt5_results[req_id] = {"ok": False, "error": str(e)}
            finally:
                _mt5_queue.task_done()
        except queue.Empty:
            pass

def _call_mt5(fn, timeout=5.0):
    """Enqueue an MT5 call and wait for the result."""
    if not MT5_AVAILABLE or not _mt5_connected:
        return {"ok": False, "error": "MT5 not connected"}
    req_id = str(uuid.uuid4())
    _mt5_queue.put((req_id, fn))
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _mt5_lock:
            if req_id in _mt5_results:
                return _mt5_results.pop(req_id)
        time.sleep(0.02)
    return {"ok": False, "error": "MT5 call timeout"}

# ── Result cache (5s TTL) ─────────────────────────────────────
_cache = {}
_CACHE_TTL = 5.0

def _cached(key, fn):
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _CACHE_TTL:
        return _cache[key]["data"]
    result = fn()
    _cache[key] = {"ts": now, "data": result}
    return result

# ── Risk state ────────────────────────────────────────────────
_risk_state = {
    "day_start_balance": CHALLENGE_START_BALANCE,
    "eq_high_water": CHALLENGE_START_BALANCE,
    "last_day": None,
}

def _update_risk_state(balance, equity):
    s = _risk_state
    if equity > s["eq_high_water"]:
        s["eq_high_water"] = equity
    today = datetime.now(timezone.utc).date()
    if s["last_day"] != today:
        s["day_start_balance"] = balance
        s["last_day"] = today
    daily_dd = max(0.0, (s["day_start_balance"] - equity) / s["day_start_balance"] * 100) \
               if s["day_start_balance"] > 0 else 0.0
    max_dd   = max(0.0, (s["eq_high_water"] - equity) / s["eq_high_water"] * 100) \
               if s["eq_high_water"] > 0 else 0.0
    return daily_dd, max_dd

# ── CSV log path discovery ────────────────────────────────────
def _find_log_dir() -> Path:
    """Locate the ISP_Logs folder written by the MT5 EA (FILE_COMMON).
    FILE_COMMON writes to: <Terminal>\Common\Files\ISP_Logs\
    terminal_info().commondata_path points directly to <Terminal>\Common
    terminal_info().data_path points to <Terminal>\<GUID> — one level up is Common's sibling
    """
    if MT5_AVAILABLE and _mt5_connected:
        res = _call_mt5(lambda m: m.terminal_info())
        if res["ok"] and res["data"]:
            info = res["data"]
            # Primary: use commondata_path attribute directly
            try:
                common = Path(info.commondata_path) / "Files" / "ISP_Logs"
                if common.exists():
                    return common
            except AttributeError:
                pass
            # Fallback: data_path is <Terminal>\<GUID>, parent is <Terminal>
            tpath = Path(info.data_path)
            common = tpath.parent / "Common" / "Files" / "ISP_Logs"
            if common.exists():
                return common
    # Last resort: local ISP_Logs folder next to this script
    local = BASE_DIR / "ISP_Logs"
    local.mkdir(exist_ok=True)
    return local

def _parse_score_from_comment(comment: str) -> float:
    """Parse trade score from EA comment like 'ISP_v3_TP1_S75' → 7.5"""
    m = re.search(r"S(\d{1,3})", comment or "")
    return int(m.group(1)) / 10.0 if m else 0.0

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()

def _ok(data) -> dict:
    return {"ok": True, "data": data, "ts": _ts()}

def _err(msg) -> dict:
    return {"ok": False, "error": msg, "ts": _ts()}

# ── Flask app ─────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*"])

@app.route("/")
def index():
    html = BASE_DIR / "ISP_CommandCenter.html"
    if html.exists():
        return send_file(html)
    return ("<h1 style='font-family:monospace;background:#05060A;color:#29B6F6;"
            "padding:40px;margin:0;min-height:100vh'>"
            "ISP Command Center<br><br>"
            "<small style='color:#7080A0'>Place ISP_CommandCenter.html next to isp_api.py "
            "and refresh.</small></h1>"), 200

# ── /api/account ─────────────────────────────────────────────
@app.route("/api/account")
def api_account():
    def _fetch(m):
        info = m.account_info()
        if info is None:
            raise RuntimeError(f"account_info() returned None: {m.last_error()}")
        return {
            "login":    info.login,
            "name":     info.name,
            "server":   info.server,
            "currency": info.currency,
            "balance":  round(info.balance, 2),
            "equity":   round(info.equity, 2),
            "profit":   round(info.profit, 2),
            "margin":   round(info.margin, 2),
            "free_margin": round(info.margin_free, 2),
            "leverage": info.leverage,
        }
    try:
        def build():
            res = _call_mt5(_fetch)
            if not res["ok"]:
                return _err(res["error"])
            d = res["data"]
            daily_dd, max_dd = _update_risk_state(d["balance"], d["equity"])
            day_start = _risk_state["day_start_balance"]
            d["day_pnl"]       = round(d["equity"] - day_start, 2)
            d["day_pnl_pct"]   = round((d["equity"] - day_start) / day_start * 100, 2) if day_start else 0
            d["daily_dd_pct"]  = round(daily_dd, 3)
            d["max_dd_pct"]    = round(max_dd, 3)
            d["daily_dd_limit"]= DAILY_DD_LIMIT
            d["max_dd_limit"]  = MAX_DD_LIMIT
            return _ok(d)
        return jsonify(_cached("account", build))
    except Exception as e:
        log.exception("account endpoint error")
        return jsonify(_err(str(e)))

# ── /api/trades ───────────────────────────────────────────────
@app.route("/api/trades")
def api_trades():
    def _fetch(m):
        positions = m.positions_get()
        if positions is None:
            return []
        result = []
        for p in positions:
            if p.magic not in ISP_MAGICS:
                continue
            result.append({
                "ticket":    p.ticket,
                "symbol":    p.symbol,
                "type":      "BUY" if p.type == 0 else "SELL",
                "lots":      round(p.volume, 2),
                "entry":     round(p.price_open, 5),
                "current":   round(p.price_current, 5),
                "sl":        round(p.sl, 5),
                "tp":        round(p.tp, 5),
                "profit":    round(p.profit, 2),
                "swap":      round(p.swap, 2),
                "magic":     p.magic,
                "comment":   p.comment,
                "score":     _parse_score_from_comment(p.comment),
                "open_time": datetime.fromtimestamp(p.time, tz=timezone.utc).isoformat(),
                "duration_min": int((time.time() - p.time) / 60),
                "is_tp1":    "TP1" in (p.comment or ""),
                "is_tp2":    "TP2" in (p.comment or ""),
            })
        return result
    try:
        def build():
            res = _call_mt5(_fetch)
            if not res["ok"]:
                return _err(res["error"])
            return _ok(res["data"])
        return jsonify(_cached("trades", build))
    except Exception as e:
        log.exception("trades endpoint error")
        return jsonify(_err(str(e)))

# ── /api/history ──────────────────────────────────────────────
@app.route("/api/history")
def api_history():
    try:
        days = int(request.args.get("days", 7))
        days = max(1, min(days, 90))

        def build():
            from_dt = datetime.now(timezone.utc) - timedelta(days=days)
            from_ts = int(from_dt.timestamp())
            to_ts   = int(time.time())

            # Try MT5 deal history
            deals = []
            def _fetch_deals(m):
                history = m.history_deals_get(from_ts, to_ts)
                if history is None:
                    return []
                return [
                    {
                        "ticket":   d.ticket,
                        "order":    d.order,
                        "symbol":   d.symbol,
                        "type":     "BUY" if d.type == 0 else "SELL",
                        "entry":    d.entry,  # 0=in, 1=out, 2=inout
                        "volume":   round(d.volume, 2),
                        "price":    round(d.price, 5),
                        "profit":   round(d.profit, 2),
                        "swap":     round(d.swap, 2),
                        "commission": round(d.commission, 2),
                        "magic":    d.magic,
                        "comment":  d.comment,
                        "score":    _parse_score_from_comment(d.comment),
                        "time":     datetime.fromtimestamp(d.time, tz=timezone.utc).isoformat(),
                    }
                    for d in history if d.magic in ISP_MAGICS and d.entry in (1, 2)
                ]

            res = _call_mt5(_fetch_deals)
            if res["ok"]:
                deals = res["data"]

            # Supplement with CSV data if available
            csv_trades = _load_csv_history(days)

            return _ok({"deals": deals, "csv_trades": csv_trades, "days": days})

        return jsonify(_cached(f"history_{days}", build))
    except Exception as e:
        log.exception("history endpoint error")
        return jsonify(_err(str(e)))

def _load_csv_history(days: int) -> list:
    """Read ISP CSV trade logs and return recent trades."""
    log_dir = _find_log_dir()
    rows = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        for csv_file in log_dir.glob("ISP_Trades_*.csv"):
            with open(csv_file, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            if len(lines) < 2:
                continue
            # MT5 FILE_CSV: header uses commas, data rows use tabs — always split header on comma
            header = [h.strip() for h in lines[0].split(",")]
            data_sep = "\t" if "\t" in lines[1] else ","
            for line in lines[1:]:
                vals = [v.strip() for v in line.split(data_sep)]
                if len(vals) < len(header):
                    continue
                row = dict(zip(header, vals))
                try:
                    dt_str = f"{row.get('Date','')} {row.get('Time','')}".strip()
                    row_dt = datetime.strptime(dt_str, "%Y.%m.%d %H:%M").replace(tzinfo=timezone.utc)
                    if row_dt >= cutoff:
                        rows.append(row)
                except (ValueError, KeyError):
                    continue
    except Exception as e:
        log.warning(f"CSV load error: {e}")
    return rows

def _load_daily_history(days: int) -> list:
    """Read ISP Daily CSV logs and return recent daily summaries."""
    log_dir = _find_log_dir()
    rows = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        for csv_file in log_dir.glob("ISP_Daily_*.csv"):
            with open(csv_file, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            if len(lines) < 2:
                continue
            header = [h.strip() for h in lines[0].split(",")]
            data_sep = "\t" if "\t" in lines[1] else ","
            for line in lines[1:]:
                vals = [v.strip() for v in line.split(data_sep)]
                if len(vals) < len(header):
                    continue
                row = dict(zip(header, vals))
                try:
                    row_dt = datetime.strptime(row.get("Date", ""), "%Y.%m.%d").replace(tzinfo=timezone.utc)
                    if row_dt >= cutoff:
                        rows.append(row)
                except (ValueError, KeyError):
                    continue
    except Exception as e:
        log.warning(f"Daily CSV load error: {e}")
    return sorted(rows, key=lambda r: r.get("Date", ""))

# ── /api/daily ────────────────────────────────────────────────
@app.route("/api/daily")
def api_daily():
    try:
        days = int(request.args.get("days", 30))
        days = max(1, min(days, 365))
        def build():
            rows = _load_daily_history(days)
            return _ok({"rows": rows, "days": days})
        return jsonify(_cached(f"daily_{days}", build))
    except Exception as e:
        log.exception("daily endpoint error")
        return jsonify(_err(str(e)))

# ── /api/compliance ───────────────────────────────────────────
@app.route("/api/compliance")
def api_compliance():
    try:
        def build():
            acct_res = _call_mt5(lambda m: m.account_info())
            if not acct_res["ok"] or acct_res["data"] is None:
                daily_dd, max_dd = 0.0, 0.0
            else:
                info = acct_res["data"]
                daily_dd, max_dd = _update_risk_state(info.balance, info.equity)

            def _firm_status(firm_daily, firm_max):
                dd_margin  = round(firm_daily - daily_dd, 2)
                max_margin = round(firm_max   - max_dd,   2)
                return {
                    "daily_dd_pct": round(daily_dd, 3),
                    "daily_limit":  firm_daily,
                    "daily_margin": dd_margin,
                    "max_dd_pct":   round(max_dd, 3),
                    "max_dd_limit": firm_max,
                    "max_margin":   max_margin,
                    "daily_pass":   daily_dd < firm_daily,
                    "max_pass":     max_dd   < firm_max,
                    "overall_pass": daily_dd < firm_daily and max_dd < firm_max,
                    "daily_pct_used": round(daily_dd / firm_daily * 100, 1) if firm_daily else 0,
                    "max_pct_used":   round(max_dd   / firm_max   * 100, 1) if firm_max   else 0,
                }

            # Our configured limits
            our = _firm_status(DAILY_DD_LIMIT, MAX_DD_LIMIT)

            firms = {
                "our_settings": {**our, "label": "Our EA Settings"},
                "FTMO":         {**_firm_status(5.0, 10.0), "label": "FTMO"},
                "E8_Markets":   {**_firm_status(4.0, 8.0),  "label": "E8 Markets"},
                "FundedNext":   {**_firm_status(5.0, 10.0), "label": "FundedNext"},
                "The5ers":      {**_firm_status(5.0, 10.0), "label": "The5ers"},
            }
            return _ok({"firms": firms, "daily_dd": round(daily_dd, 3), "max_dd": round(max_dd, 3)})

        return jsonify(_cached("compliance", build))
    except Exception as e:
        log.exception("compliance endpoint error")
        return jsonify(_err(str(e)))

# ── /api/status ───────────────────────────────────────────────
@app.route("/api/status")
def api_status():
    try:
        import psutil
        psutil_ok = True
    except ImportError:
        psutil_ok = False

    status = {
        "api":       True,
        "mt5":       False,
        "sentiment": False,
        "monitor":   False,
        "mt5_terminal": None,
        "mt5_account":  None,
        "log_dir":   str(_find_log_dir()),
    }

    # MT5 status
    if MT5_AVAILABLE and _mt5_connected:
        res = _call_mt5(lambda m: m.terminal_info())
        if res["ok"] and res["data"]:
            t = res["data"]
            status["mt5"] = True
            status["mt5_terminal"] = {"name": t.name, "build": t.build, "connected": t.connected}
            acct = _call_mt5(lambda m: m.account_info())
            if acct["ok"] and acct["data"]:
                a = acct["data"]
                status["mt5_account"] = {"login": a.login, "server": a.server, "balance": a.balance}

    # Sentiment service
    try:
        r = requests.get(f"http://localhost:{SENTIMENT_PORT}/health", timeout=2)
        status["sentiment"] = r.status_code == 200
    except Exception:
        pass

    # Monitor process
    if psutil_ok:
        import psutil
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                cmd = " ".join(proc.info["cmdline"] or [])
                if "isp_monitor" in cmd:
                    status["monitor"] = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    # CSV freshness (last log write within 2 hours = active)
    log_dir = _find_log_dir()
    newest_mtime = 0
    for f in log_dir.glob("*.csv"):
        mtime = f.stat().st_mtime
        if mtime > newest_mtime:
            newest_mtime = mtime
    status["log_fresh"]        = (time.time() - newest_mtime) < 7200 if newest_mtime else False
    status["log_last_update"]  = datetime.fromtimestamp(newest_mtime, tz=timezone.utc).isoformat() \
                                  if newest_mtime else None

    return jsonify(_ok(status))

# ── /api/session ──────────────────────────────────────────────
@app.route("/api/session")
def api_session():
    """Current session status based on UTC time."""
    try:
        gmt_offset = int(os.getenv("GMT_OFFSET", "3"))
        utc_now = datetime.now(timezone.utc)
        hr = utc_now.hour
        london = (8 <= hr < 11)
        ny     = (13 <= hr < 16)
        sessions = {
            "utc_time":    utc_now.isoformat(),
            "utc_hour":    hr,
            "london":      london,
            "ny":          ny,
            "in_session":  london or ny,
            "session_name": "London" if london else ("New York" if ny else "Off-Session"),
            "london_open":  "08:00 UTC",
            "london_close": "11:00 UTC",
            "ny_open":      "13:00 UTC",
            "ny_close":     "16:00 UTC",
        }
        return jsonify(_ok(sessions))
    except Exception as e:
        return jsonify(_err(str(e)))

# ── /api/sentiment (proxy to avoid CORS) ──────────────────────
@app.route("/api/sentiment")
def api_sentiment():
    try:
        r = requests.get(f"http://localhost:{SENTIMENT_PORT}/sentiment/all", timeout=5)
        return jsonify({"ok": True, "data": r.json(), "ts": _ts()})
    except Exception as e:
        log.warning(f"Sentiment proxy error: {e}")
        return jsonify({"ok": False, "error": str(e), "ts": _ts()})

# ── /api/news (proxy ForexFactory to avoid CORS) ──────────────
@app.route("/api/news")
def api_news():
    try:
        r = requests.get(
            "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
            timeout=10,
            headers={"User-Agent": "ISP-Dashboard/1.0"}
        )
        events = [
            {
                "title":    e.get("title", ""),
                "country":  e.get("country", ""),
                "date":     e.get("date", ""),
                "impact":   e.get("impact", ""),
                "previous": e.get("previous", ""),
                "forecast": e.get("forecast", ""),
            }
            for e in r.json() if e.get("impact") == "High"
        ]
        return jsonify({"ok": True, "data": events, "ts": _ts()})
    except Exception as e:
        log.warning(f"News proxy error: {e}")
        return jsonify({"ok": False, "error": str(e), "ts": _ts()})

# ── Startup ───────────────────────────────────────────────────
if __name__ == "__main__":
    if MT5_AVAILABLE:
        t = threading.Thread(target=_mt5_worker, daemon=True, name="MT5Worker")
        t.start()
        time.sleep(1.5)  # Give MT5 time to initialize
    log.info(f"ISP API starting on http://localhost:{API_PORT}")
    app.run(host="0.0.0.0", port=API_PORT, debug=False, threaded=True)
