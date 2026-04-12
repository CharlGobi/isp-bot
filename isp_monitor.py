"""
ISP Phase 4 — Multi-Symbol Monitor & Telegram Alerts
Monitors all 4 pairs in real time, tracks prop firm progress,
sends Telegram alerts with setup chart screenshots.

Features:
  - Real-time equity/drawdown tracking per pair
  - Telegram text alerts on trade signals, fills, and closes
  - Chart screenshot generation (matplotlib) on each alert
  - Prop firm compliance dashboard summary every hour
  - Daily P&L summary at 17:00 UTC

Setup:
  1. Create Telegram bot: talk to @BotFather on Telegram
  2. Get your chat ID: talk to @userinfobot on Telegram
  3. Set env vars:
       export TELEGRAM_TOKEN="your_bot_token"
       export TELEGRAM_CHAT_ID="your_chat_id"
       export MT5_PASSWORD="your_mt5_password"
       export MT5_SERVER="Exness-MT5Trial9"
       export MT5_LOGIN="435152190"

Install:
  pip install MetaTrader5 python-telegram-bot requests matplotlib pandas schedule

Run:
  python isp_monitor.py
"""

import asyncio
import io
import json
import logging
import os
import schedule
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("isp_monitor.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("ISP.Monitor")

# ── Config ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
MT5_LOGIN        = int(os.getenv("MT5_LOGIN",    "435152190"))
MT5_PASSWORD     = os.getenv("MT5_PASSWORD",     "")
MT5_SERVER       = os.getenv("MT5_SERVER",       "Exness-MT5Trial9")
MAGIC_NUMBER     = 202601

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
MAGIC_MAP = {
    "EURUSD": 202601,
    "GBPUSD": 202602,
    "USDJPY": 202603,
    "XAUUSD": 202604,
}

# Prop firm limits
DAILY_DD_LIMIT = 3.0
MAX_DD_LIMIT   = 8.0
CHALLENGE_START_BALANCE = 10000.0  # Update per challenge

# State file for persistence across restarts
STATE_PATH = Path("isp_data/monitor_state.json")
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── State ────────────────────────────────────────────────────────────────────
state = {
    "day_start_balance":  CHALLENGE_START_BALANCE,
    "equity_high":        CHALLENGE_START_BALANCE,
    "last_positions":     {},
    "today_trades":       [],
    "alert_history":      [],
    "last_daily_summary": None,
    "last_compliance_msg": None,
}


def load_state():
    global state
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH) as f:
                saved = json.load(f)
            state.update(saved)
            log.info("State loaded from disk.")
        except Exception as e:
            log.warning(f"State load failed: {e}")


def save_state():
    try:
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2, default=str)
    except Exception as e:
        log.error(f"State save failed: {e}")


# ── Telegram messenger ───────────────────────────────────────────────────────

def send_telegram(text: str, parse_mode: str = "HTML") -> bool:
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN":
        log.info(f"[TELEGRAM MOCK] {text[:120]}...")
        return True

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": parse_mode,
    }
    for attempt in range(3):
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 429:
                retry_after = r.json().get("parameters", {}).get("retry_after", 30)
                log.warning(f"Telegram flood control: waiting {retry_after}s (attempt {attempt+1}/3)")
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Telegram send failed (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return False


def send_telegram_photo(buf: io.BytesIO, caption: str) -> bool:
    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN":
        log.info(f"[TELEGRAM MOCK PHOTO] {caption[:80]}")
        return True

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    for attempt in range(3):
        buf.seek(0)
        try:
            r = requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024], "parse_mode": "HTML"},
                files={"photo": ("chart.png", buf, "image/png")},
                timeout=15
            )
            if r.status_code == 429:
                retry_after = r.json().get("parameters", {}).get("retry_after", 30)
                log.warning(f"Telegram photo flood control: waiting {retry_after}s (attempt {attempt+1}/3)")
                time.sleep(retry_after)
                continue
            r.raise_for_status()
            return True
        except Exception as e:
            log.error(f"Telegram photo send failed (attempt {attempt+1}/3): {e}")
            if attempt < 2:
                time.sleep(5)
    return False


# ── MT5 connection ───────────────────────────────────────────────────────────

def connect_mt5() -> bool:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        log.warning("MetaTrader5 not installed. Running in simulation mode.")
        return False

    if not mt5.initialize():
        log.error(f"MT5 init failed: {mt5.last_error()}")
        return False

    if MT5_PASSWORD:
        if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            log.error(f"MT5 login failed: {mt5.last_error()}")
            return False

    log.info(f"MT5 connected: {MT5_SERVER} | Account: {MT5_LOGIN}")
    return True


def get_account_info() -> dict:
    try:
        import MetaTrader5 as mt5
        info = mt5.account_info()
        if info is None:
            return {}
        return {
            "balance":  info.balance,
            "equity":   info.equity,
            "margin":   info.margin,
            "free_margin": info.margin_free,
            "profit":   info.profit,
        }
    except Exception:
        # Simulation mode
        return {
            "balance":  10075.83,
            "equity":   10075.83,
            "margin":   0,
            "free_margin": 10075.83,
            "profit":   0,
        }


def get_open_positions() -> list:
    try:
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        if positions is None:
            return []
        result = []
        for p in positions:
            if p.magic in MAGIC_MAP.values():
                result.append({
                    "ticket":    p.ticket,
                    "symbol":    p.symbol,
                    "type":      "BUY" if p.type == 0 else "SELL",
                    "volume":    p.volume,
                    "price_open": p.price_open,
                    "sl":        p.sl,
                    "tp":        p.tp,
                    "profit":    p.profit,
                    "comment":   p.comment,
                    "magic":     p.magic,
                    "time":      datetime.fromtimestamp(p.time).isoformat(),
                })
        return result
    except Exception:
        return []


def get_recent_history(hours: int = 24) -> list:
    try:
        import MetaTrader5 as mt5
        from_time = datetime.utcnow() - timedelta(hours=hours)
        deals = mt5.history_deals_get(from_time, datetime.utcnow())
        if deals is None:
            return []
        return [d for d in deals if d.magic in MAGIC_MAP.values()]
    except Exception:
        return []


def get_ohlcv_for_chart(symbol: str, bars: int = 80) -> pd.DataFrame:
    try:
        import MetaTrader5 as mt5
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, bars)
        if rates is None or len(rates) == 0:
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df
    except Exception:
        # Generate synthetic OHLCV for demo
        n = bars
        np.random.seed(42)
        close = 1.09 + np.cumsum(np.random.randn(n) * 0.0003)
        high  = close + np.abs(np.random.randn(n) * 0.0002)
        low   = close - np.abs(np.random.randn(n) * 0.0002)
        open_ = close - np.random.randn(n) * 0.0001
        df = pd.DataFrame({
            "time":  pd.date_range("2026-04-08", periods=n, freq="5min"),
            "open":  open_, "high": high, "low": low, "close": close,
            "tick_volume": np.random.randint(100, 500, n)
        })
        return df


# ── Chart generator ──────────────────────────────────────────────────────────

def generate_setup_chart(symbol: str, signal: str, score: float, regime: str,
                          entry: float, sl: float, tp1: float, tp2: float) -> io.BytesIO:
    """
    Generate a candlestick chart with EMA lines and trade setup levels.
    Returns PNG as BytesIO buffer.
    """
    df = get_ohlcv_for_chart(symbol, 60)

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                   gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor("#05060A")
    ax.set_facecolor("#0C0E14")
    ax2.set_facecolor("#0C0E14")

    # ── Draw candles ──────────────────────────────────────────────────────
    if not df.empty:
        x = np.arange(len(df))
        for i, row in df.iterrows():
            idx = list(df.index).index(i)
            color = "#00E676" if row["close"] >= row["open"] else "#FF3D57"
            ax.plot([idx, idx], [row["low"], row["high"]], color=color, linewidth=1)
            ax.add_patch(plt.Rectangle(
                (idx - 0.35, min(row["open"], row["close"])),
                0.7, abs(row["close"] - row["open"]),
                facecolor=color, edgecolor=color, alpha=0.9
            ))

        close = df["close"]
        ema9  = close.ewm(span=9,  adjust=False).mean()
        ema21 = close.ewm(span=21, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        ax.plot(x, ema9.values,  color="#FFD740", linewidth=1.2, label="EMA 9",  alpha=0.9)
        ax.plot(x, ema21.values, color="#29B6F6", linewidth=1.5, label="EMA 21", alpha=0.9)
        ax.plot(x, ema50.values, color="#9C6EFA", linewidth=1.2, label="EMA 50", alpha=0.7)

        # Volume bars
        vol_color = ["#00E67640" if df.iloc[i]["close"] >= df.iloc[i]["open"] else "#FF3D5740"
                     for i in range(len(df))]
        ax2.bar(x, df["tick_volume"], color=vol_color, width=0.8)
        ax2.set_facecolor("#0C0E14")
        ax2.tick_params(colors="#7080A0")
        ax2.set_ylabel("Volume", color="#7080A0", fontsize=9)
        for spine in ax2.spines.values():
            spine.set_color("#1C2030")

    # ── Trade levels ──────────────────────────────────────────────────────
    last_x = len(df) - 1
    ax.axhline(entry, color="#FFFFFF", linewidth=1.5, linestyle="--", alpha=0.9, label=f"Entry {entry:.5f}")
    ax.axhline(sl,    color="#FF3D57", linewidth=1.5, linestyle="--", alpha=0.9, label=f"SL {sl:.5f}")
    ax.axhline(tp1,   color="#00E676", linewidth=1.2, linestyle=":",  alpha=0.8, label=f"TP1 {tp1:.5f}")
    ax.axhline(tp2,   color="#00A854", linewidth=1.5, linestyle="--", alpha=0.9, label=f"TP2 {tp2:.5f}")

    # ── Labels ────────────────────────────────────────────────────────────
    label_x = last_x + 1.5
    price_range = ax.get_ylim()
    for price, label, color in [
        (entry, f"ENTRY {entry:.5f}", "#FFFFFF"),
        (sl,    f"SL {sl:.5f}",      "#FF3D57"),
        (tp1,   f"TP1 {tp1:.5f}",    "#00E676"),
        (tp2,   f"TP2 {tp2:.5f}",    "#00A854"),
    ]:
        ax.text(last_x + 0.5, price, label, color=color, fontsize=8,
                fontfamily="monospace", va="center",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="#0C0E14", edgecolor=color, alpha=0.8))

    # ── Title ──────────────────────────────────────────────────────────────
    sig_color = "#00E676" if signal == "BUY" else "#FF3D57"
    ax.set_title(
        f"⚡ ISP EA  |  {symbol}  |  {signal}  |  Score: {score:.1f}/10  |  {regime}  |  M5",
        color=sig_color, fontsize=13, fontweight="bold", fontfamily="monospace", pad=10
    )

    # ── Styling ────────────────────────────────────────────────────────────
    ax.tick_params(colors="#7080A0", labelsize=8)
    ax.set_xlabel("")
    ax.legend(loc="upper left", fontsize=8, facecolor="#10131C", edgecolor="#1C2030",
              labelcolor="#D0D8F0", framealpha=0.9)
    ax.yaxis.set_label_position("right")
    ax.yaxis.tick_right()
    for spine in ax.spines.values():
        spine.set_color("#1C2030")

    # Timestamp
    fig.text(0.01, 0.01, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
             color="#404860", fontsize=8, fontfamily="monospace")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_equity_chart(trades: list, balance: float, equity: float,
                           daily_dd: float, max_dd: float) -> io.BytesIO:
    """Generate equity curve for daily summary."""
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(12, 7),
                                   gridspec_kw={"height_ratios": [2, 1]})
    fig.patch.set_facecolor("#05060A")
    ax.set_facecolor("#0C0E14")
    ax2.set_facecolor("#0C0E14")

    if trades:
        bal = CHALLENGE_START_BALANCE
        curve = [bal]
        times = ["Start"]
        pnls  = []
        for t in sorted(trades, key=lambda x: x.get("time", "")):
            bal += t.get("profit", 0)
            curve.append(bal)
            times.append(t.get("time", "")[:10])
            pnls.append(t.get("profit", 0))

        x = np.arange(len(curve))
        ax.fill_between(x, CHALLENGE_START_BALANCE, curve,
                         where=[c >= CHALLENGE_START_BALANCE for c in curve],
                         color="#00E676", alpha=0.2)
        ax.fill_between(x, CHALLENGE_START_BALANCE, curve,
                         where=[c < CHALLENGE_START_BALANCE for c in curve],
                         color="#FF3D57", alpha=0.2)
        ax.plot(x, curve, color="#29B6F6", linewidth=2)
        ax.axhline(CHALLENGE_START_BALANCE, color="#7080A0", linewidth=1, linestyle="--", alpha=0.6)

        # P&L bars
        colors = ["#00E67680" if p >= 0 else "#FF3D5780" for p in pnls]
        ax2.bar(np.arange(len(pnls)), pnls, color=colors)
        ax2.axhline(0, color="#7080A0", linewidth=1)
        ax2.set_ylabel("Trade P&L", color="#7080A0", fontsize=9)

    ax.set_title(f"⚡ ISP EA — Equity Curve | Balance: ${balance:.2f} | DD: {daily_dd:.2f}% day / {max_dd:.2f}% max",
                  color="#D0D8F0", fontsize=12, fontweight="bold", fontfamily="monospace")
    for a in [ax, ax2]:
        a.tick_params(colors="#7080A0", labelsize=8)
        for spine in a.spines.values():
            spine.set_color("#1C2030")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Alert formatters ──────────────────────────────────────────────────────────

def fmt_signal_alert(symbol, signal, score, regime, bias, session,
                      entry, sl, tp1, tp2, lots, daily_dd, max_dd) -> str:
    dir_emoji = "🟢" if signal == "BUY" else "🔴"
    score_bar = "▓" * int(score) + "░" * (10 - int(score))
    return f"""⚡ <b>ISP SIGNAL</b> {dir_emoji}

<b>Symbol:</b>  {symbol}
<b>Direction:</b>  {signal}
<b>Lots:</b>  {lots:.2f}

📍 <b>Levels</b>
  Entry:  <code>{entry:.5f}</code>
  SL:     <code>{sl:.5f}</code>
  TP1:    <code>{tp1:.5f}</code>  (1R)
  TP2:    <code>{tp2:.5f}</code>  (2.5R)

📊 <b>Context</b>
  Score:   <code>{score:.1f}/10</code>  {score_bar}
  Regime:  <code>{regime}</code>
  Bias:    <code>{bias}</code>
  Session: <code>{session}</code>

🛡 <b>Risk</b>
  Day DD:  <code>{daily_dd:.2f}% / 3.0%</code>
  Max DD:  <code>{max_dd:.2f}% / 8.0%</code>

⏰ {datetime.utcnow().strftime('%H:%M UTC')}"""


def fmt_trade_closed(symbol, direction, profit, pips, reason, daily_dd, max_dd, consec) -> str:
    result  = "WIN ✅" if profit >= 0 else "LOSS ❌"
    p_color = "🟢" if profit >= 0 else "🔴"
    return f"""{p_color} <b>ISP TRADE CLOSED</b>

<b>Symbol:</b>  {symbol}  |  {direction}
<b>Result:</b>  {result}
<b>P&L:</b>  <code>{"+" if profit>=0 else ""}{profit:.2f}</code>  ({("+" if pips>=0 else "")}{pips:.1f} pips)
<b>Reason:</b>  {reason}
<b>Consec losses:</b>  {consec}

🛡 Day DD: <code>{daily_dd:.2f}%</code>  |  Max DD: <code>{max_dd:.2f}%</code>
⏰ {datetime.utcnow().strftime('%H:%M UTC')}"""


def fmt_halt_alert(reason, daily_dd, max_dd, equity) -> str:
    return f"""🚨 <b>ISP TRADING HALTED</b>

<b>Reason:</b>  <code>{reason}</code>
<b>Day DD:</b>  <code>{daily_dd:.2f}%</code>
<b>Max DD:</b>  <code>{max_dd:.2f}%</code>
<b>Equity:</b>  <code>${equity:.2f}</code>

Bot has stopped all trading.
Review your account immediately.
⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"""


def fmt_daily_summary(trades: list, balance: float, equity: float,
                       daily_dd: float, max_dd: float, session_pnl: dict) -> str:
    wins   = [t for t in trades if t.get("profit", 0) > 0]
    losses = [t for t in trades if t.get("profit", 0) <= 0]
    tp     = sum(t.get("profit", 0) for t in trades)
    wr     = (len(wins) / len(trades) * 100) if trades else 0

    eu_pnl = session_pnl.get("EURUSD", 0)
    gb_pnl = session_pnl.get("GBPUSD", 0)
    uj_pnl = session_pnl.get("USDJPY", 0)
    xau_pnl= session_pnl.get("XAUUSD", 0)

    status = "🟢 ACTIVE" if max_dd < MAX_DD_LIMIT and daily_dd < DAILY_DD_LIMIT else "🔴 HALTED"

    return f"""📋 <b>ISP DAILY SUMMARY</b>  {datetime.utcnow().strftime('%Y-%m-%d')}

<b>Account</b>
  Balance:  <code>${balance:.2f}</code>
  Equity:   <code>${equity:.2f}</code>
  Day P&L:  <code>{"+" if tp>=0 else ""}{tp:.2f}</code>

<b>Trading</b>
  Trades:   <code>{len(trades)}</code>  ({len(wins)}W / {len(losses)}L)
  Win Rate: <code>{wr:.1f}%</code>
  Status:   {status}

<b>Pair Breakdown</b>
  EURUSD:   <code>{"+" if eu_pnl>=0 else ""}{eu_pnl:.2f}</code>
  GBPUSD:   <code>{"+" if gb_pnl>=0 else ""}{gb_pnl:.2f}</code>
  USDJPY:   <code>{"+" if uj_pnl>=0 else ""}{uj_pnl:.2f}</code>
  XAUUSD:   <code>{"+" if xau_pnl>=0 else ""}{xau_pnl:.2f}</code>

<b>Risk</b>
  Day DD:  <code>{daily_dd:.2f}% / 3.0%</code>
  Max DD:  <code>{max_dd:.2f}% / 8.0%</code>

⏰ Generated: {datetime.utcnow().strftime('%H:%M UTC')}"""


def fmt_compliance_check(balance, equity, daily_dd, max_dd, open_trades) -> str:
    def chk(ok): return "✅" if ok else "❌"
    return f"""🛡 <b>ISP COMPLIANCE CHECK</b>

  Daily DD:   {chk(daily_dd < DAILY_DD_LIMIT)} <code>{daily_dd:.2f}%</code> / 3.0%
  Max DD:     {chk(max_dd < MAX_DD_LIMIT)} <code>{max_dd:.2f}%</code> / 8.0%
  Open trades:{chk(open_trades <= 2)} <code>{open_trades}</code> / 2 max
  Equity:     <code>${equity:.2f}</code>

  FTMO:       {chk(daily_dd<5 and max_dd<10)} Pass
  E8 Markets: {chk(daily_dd<3 and max_dd<8)} Pass
  FundedNext: {chk(daily_dd<5 and max_dd<10)} Pass
  The5ers:    {chk(daily_dd<5 and max_dd<10)} Pass

⏰ {datetime.utcnow().strftime('%H:%M UTC')}"""


# ── Monitor loop ─────────────────────────────────────────────────────────────

last_positions_snapshot = {}

def monitor_tick():
    """Called every 30 seconds. Checks for new positions, closed trades, DD limits."""
    global last_positions_snapshot

    acct = get_account_info()
    if not acct:
        return

    equity  = acct.get("equity",  state["day_start_balance"])
    balance = acct.get("balance", state["day_start_balance"])

    # Update high water mark
    if equity > state["equity_high"]:
        state["equity_high"] = equity

    daily_dd = max(0, (state["day_start_balance"] - equity) / state["day_start_balance"] * 100)
    max_dd   = max(0, (state["equity_high"] - equity) / state["equity_high"] * 100)

    open_pos = get_open_positions()
    current_tickets = {p["ticket"]: p for p in open_pos}

    # Detect new positions opened
    for ticket, pos in current_tickets.items():
        if ticket not in last_positions_snapshot:
            log.info(f"New position detected: {pos['symbol']} {pos['type']} #{ticket}")
            # We don't have full signal data here, send simple alert
            msg = f"""📥 <b>ISP TRADE OPENED</b>

<b>Symbol:</b>  {pos['symbol']}  |  {pos['type']}
<b>Lots:</b>    <code>{pos['volume']:.2f}</code>
<b>Entry:</b>   <code>{pos['price_open']:.5f}</code>
<b>SL:</b>      <code>{pos['sl']:.5f}</code>
<b>TP:</b>      <code>{pos['tp']:.5f}</code>
<b>Comment:</b> <code>{pos['comment']}</code>
⏰ {datetime.utcnow().strftime('%H:%M UTC')}"""
            send_telegram(msg)

    # Detect closed positions
    for ticket, pos in last_positions_snapshot.items():
        if ticket not in current_tickets:
            log.info(f"Position closed: {pos['symbol']} #{ticket}")
            # Get result from history
            deals = get_recent_history(hours=1)
            profit = pos.get("profit", 0)
            for d in deals:
                if hasattr(d, "position_id") and d.position_id == ticket:
                    profit = d.profit
                    break
            pips = profit / (pos["volume"] * 10)  # Rough estimate
            msg = fmt_trade_closed(
                pos["symbol"], pos["type"], profit, pips,
                "Closed", daily_dd, max_dd, 0
            )
            send_telegram(msg)

    last_positions_snapshot = current_tickets

    # Drawdown alerts
    if daily_dd >= DAILY_DD_LIMIT * 0.8:
        msg = f"⚠️ <b>ISP WARNING:</b> Daily DD at <code>{daily_dd:.2f}%</code> (limit: {DAILY_DD_LIMIT}%)"
        send_telegram(msg)

    if max_dd >= MAX_DD_LIMIT:
        msg = fmt_halt_alert("MAX DD REACHED", daily_dd, max_dd, equity)
        send_telegram(msg)

    save_state()


def daily_summary():
    """Sends daily P&L summary at 17:00 UTC."""
    acct   = get_account_info()
    equity = acct.get("equity",  state["day_start_balance"])
    balance= acct.get("balance", state["day_start_balance"])
    daily_dd = max(0, (state["day_start_balance"] - equity) / state["day_start_balance"] * 100)
    max_dd   = max(0, (state["equity_high"] - equity) / state["equity_high"] * 100)

    deals  = get_recent_history(hours=24)
    trades = [{"profit": getattr(d, "profit", 0), "symbol": getattr(d, "symbol", ""),
               "time":   str(getattr(d, "time", ""))} for d in deals]

    sym_pnl = {}
    for t in trades:
        sym = t.get("symbol", "")
        sym_pnl[sym] = sym_pnl.get(sym, 0) + t.get("profit", 0)

    msg = fmt_daily_summary(trades, balance, equity, daily_dd, max_dd, sym_pnl)
    chart_buf = generate_equity_chart(trades, balance, equity, daily_dd, max_dd)
    send_telegram_photo(chart_buf, caption=f"ISP Daily Equity — {datetime.utcnow().strftime('%Y-%m-%d')}")
    send_telegram(msg)

    # Reset day start
    state["day_start_balance"] = balance
    state["today_trades"] = []
    save_state()
    log.info("Daily summary sent.")


def hourly_compliance():
    """Sends compliance check every hour."""
    acct   = get_account_info()
    equity = acct.get("equity",  state["day_start_balance"])
    balance= acct.get("balance", state["day_start_balance"])
    daily_dd = max(0, (state["day_start_balance"] - equity) / state["day_start_balance"] * 100)
    max_dd   = max(0, (state["equity_high"] - equity) / state["equity_high"] * 100)
    n_open = len(get_open_positions())
    msg = fmt_compliance_check(balance, equity, daily_dd, max_dd, n_open)
    send_telegram(msg)
    log.info("Hourly compliance check sent.")


# ── Entry point ──────────────────────────────────────────────────────────────

def run():
    log.info("=== ISP Monitor Starting ===")
    log.info(f"Symbols: {SYMBOLS}")
    log.info(f"Telegram: {'configured' if TELEGRAM_TOKEN != 'YOUR_BOT_TOKEN' else 'not configured (mock mode)'}")
    log.info(f"MT5: Login {MT5_LOGIN} | Server {MT5_SERVER}")

    load_state()
    connect_mt5()

    # Schedule tasks
    schedule.every(30).seconds.do(monitor_tick)
    schedule.every().day.at("17:00").do(daily_summary)
    schedule.every().hour.do(hourly_compliance)

    # Send startup message
    startup_msg = f"""🚀 <b>ISP Monitor Online</b>

Monitoring: <code>{", ".join(SYMBOLS)}</code>
Daily DD limit:  <code>{DAILY_DD_LIMIT}%</code>
Max DD limit:    <code>{MAX_DD_LIMIT}%</code>
Start balance:   <code>${CHALLENGE_START_BALANCE:.2f}</code>
⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"""
    send_telegram(startup_msg)

    log.info("Monitor running. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run()
