"""
ISP Launcher — isp_launcher.py
One-command startup for the entire ISP system.

Starts 3 services:
  1. isp_sentiment_service.py  (port 5050)
  2. isp_monitor.py            (Telegram alerts)
  3. isp_api.py                (port 5051 + serves dashboard)

Usage:
  python isp_launcher.py              # Start everything
  python isp_launcher.py --check      # Validate config only, then exit

Dashboard: http://localhost:5051
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── ANSI colors — works on Windows Terminal, PowerShell 7+, all Linux/Mac ─────
os.system("")  # Activate ANSI on Windows legacy cmd.exe
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓ PASS{RESET}  {msg}")
def fail(msg):  print(f"  {RED}✗ FAIL{RESET}  {msg}")
def warn(msg):  print(f"  {YELLOW}⚠ WARN{RESET}  {msg}")
def info(msg):  print(f"  {CYAN}  INFO{RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{CYAN}{msg}{RESET}")

BASE_DIR = Path(__file__).parent

# ── Load .env ──────────────────────────────────────────────────
env_file = BASE_DIR / ".env"
if env_file.exists():
    load_dotenv(env_file)
    info(f"Config loaded from {env_file}")
else:
    warn(".env file not found — using environment variables or defaults")

# ── Config ─────────────────────────────────────────────────────
MT5_LOGIN    = os.getenv("MT5_LOGIN",    "")
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER   = os.getenv("MT5_SERVER",   "")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN",   "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
ALPHAVANTAGE_KEY = os.getenv("ALPHAVANTAGE_KEY",  "YOUR_KEY_HERE")
DAILY_DD_LIMIT   = os.getenv("DAILY_DD_LIMIT",   "3.0")
MAX_DD_LIMIT     = os.getenv("MAX_DD_LIMIT",     "8.0")
CHALLENGE_START  = os.getenv("CHALLENGE_START_BALANCE", "10000")
API_PORT         = int(os.getenv("API_PORT",         "5051"))
SENTIMENT_PORT   = int(os.getenv("SENTIMENT_PORT",   "5050"))
AUTO_RESTART     = os.getenv("AUTO_RESTART", "true").lower() == "true"

SERVICES = [
    {
        "name":    "Sentiment Service",
        "script":  BASE_DIR / "isp_sentiment_service.py",
        "port":    SENTIMENT_PORT,
        "health":  f"http://localhost:{SENTIMENT_PORT}/health",
        "logfile": BASE_DIR / "isp_sentiment.log",
    },
    {
        "name":    "Monitor / Telegram",
        "script":  BASE_DIR / "isp_monitor.py",
        "port":    None,           # No HTTP port — checked by process scan
        "health":  None,
        "logfile": BASE_DIR / "isp_monitor.log",
    },
    {
        "name":    "API + Dashboard",
        "script":  BASE_DIR / "isp_api.py",
        "port":    API_PORT,
        "health":  f"http://localhost:{API_PORT}/api/status",
        "logfile": BASE_DIR / "isp_api.log",
    },
]

_procs = []  # Running subprocess handles

# ── Config validation ──────────────────────────────────────────
def validate_config() -> bool:
    header("Validating configuration…")
    passed = True

    if not MT5_LOGIN or not MT5_LOGIN.isdigit():
        fail("MT5_LOGIN is missing or not a number"); passed = False
    else:
        ok(f"MT5_LOGIN = {MT5_LOGIN}")

    if not MT5_PASSWORD:
        fail("MT5_PASSWORD is empty"); passed = False
    else:
        ok("MT5_PASSWORD is set")

    if not MT5_SERVER:
        fail("MT5_SERVER is empty"); passed = False
    else:
        ok(f"MT5_SERVER = {MT5_SERVER}")

    try:
        daily = float(DAILY_DD_LIMIT)
        maxdd = float(MAX_DD_LIMIT)
        bal   = float(CHALLENGE_START)
        if daily <= 0 or daily >= maxdd:
            fail(f"DAILY_DD_LIMIT ({daily}) must be > 0 and < MAX_DD_LIMIT ({maxdd})"); passed = False
        else:
            ok(f"Risk limits: daily={daily}%  max={maxdd}%  start_balance=${bal:,.0f}")
    except ValueError:
        fail("DAILY_DD_LIMIT or MAX_DD_LIMIT or CHALLENGE_START_BALANCE is not a number"); passed = False

    if TELEGRAM_TOKEN == "YOUR_BOT_TOKEN":
        warn("TELEGRAM_TOKEN not configured — monitor will run without Telegram alerts")
    else:
        ok("TELEGRAM_TOKEN configured")

    if TELEGRAM_CHAT_ID == "YOUR_CHAT_ID":
        warn("TELEGRAM_CHAT_ID not configured")

    if ALPHAVANTAGE_KEY == "YOUR_KEY_HERE":
        warn("ALPHAVANTAGE_KEY not configured — sentiment service uses simulated data")
    else:
        ok("ALPHAVANTAGE_KEY configured")

    # Check Python imports
    print()
    header("Checking Python dependencies…")
    for pkg, imp in [
        ("flask",            "flask"),
        ("flask_cors",       "flask_cors"),
        ("python-dotenv",    "dotenv"),
        ("requests",         "requests"),
        ("schedule",         "schedule"),
        ("MetaTrader5",      "MetaTrader5"),
        ("psutil",           "psutil"),
    ]:
        try:
            __import__(imp)
            ok(pkg)
        except ImportError:
            if pkg == "MetaTrader5":
                warn(f"MetaTrader5 not installed (Windows-only) — API runs in offline mode")
            else:
                fail(f"{pkg} not installed — run: pip install -r requirements.txt")
                passed = False

    return passed

# ── Service startup ────────────────────────────────────────────
def _wait_for_port(url: str, timeout: float = 15.0) -> bool:
    if not url:
        return True  # No health check for this service
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False

def start_services():
    header("Starting ISP services…")
    for svc in SERVICES:
        script = svc["script"]
        if not script.exists():
            fail(f"{svc['name']}: script not found at {script}"); continue

        logfile = open(svc["logfile"], "a", buffering=1)
        proc = subprocess.Popen(
            [sys.executable, str(script)],
            stdout=logfile,
            stderr=logfile,
            cwd=str(BASE_DIR),
        )
        _procs.append({"svc": svc, "proc": proc, "log": logfile})
        info(f"{svc['name']} started (PID {proc.pid}) — log: {svc['logfile'].name}")
        time.sleep(2.0)  # Brief pause before health check

        if svc["health"]:
            if _wait_for_port(svc["health"]):
                ok(f"{svc['name']} is responsive at {svc['health']}")
            else:
                warn(f"{svc['name']} health check timed out — check {svc['logfile'].name}")
        else:
            ok(f"{svc['name']} started")

# ── Watchdog loop ──────────────────────────────────────────────
def watchdog():
    header("All services started")
    print(f"\n{BOLD}  Dashboard: {CYAN}http://localhost:{API_PORT}{RESET}")
    print(f"{DIM}  Press Ctrl+C to stop all services{RESET}\n")

    while True:
        time.sleep(30)
        for entry in _procs:
            proc = entry["proc"]
            svc  = entry["svc"]
            if proc.poll() is not None:
                exit_code = proc.poll()
                warn(f"{svc['name']} EXITED (code {exit_code})")
                if AUTO_RESTART:
                    warn(f"Auto-restarting {svc['name']}…")
                    script = svc["script"]
                    logfile = open(svc["logfile"], "a", buffering=1)
                    new_proc = subprocess.Popen(
                        [sys.executable, str(script)],
                        stdout=logfile,
                        stderr=logfile,
                        cwd=str(BASE_DIR),
                    )
                    entry["proc"] = new_proc
                    entry["log"] = logfile
                    time.sleep(2)
                    if new_proc.poll() is None:
                        ok(f"{svc['name']} restarted (PID {new_proc.pid})")
                    else:
                        fail(f"{svc['name']} restart failed — check {svc['logfile'].name}")

# ── Graceful shutdown ──────────────────────────────────────────
def shutdown(signum=None, frame=None):
    print(f"\n{YELLOW}Stopping all services…{RESET}")
    for entry in _procs:
        proc = entry["proc"]
        svc  = entry["svc"]
        if proc.poll() is None:
            try:
                proc.terminate()
                info(f"Sent SIGTERM to {svc['name']} (PID {proc.pid})")
            except Exception:
                pass
        try:
            entry["log"].close()
        except Exception:
            pass

    # Wait up to 5s for graceful shutdown
    deadline = time.time() + 5.0
    for entry in _procs:
        remaining = max(0, deadline - time.time())
        try:
            entry["proc"].wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            try:
                entry["proc"].kill()
                warn(f"Force-killed {entry['svc']['name']}")
            except Exception:
                pass

    print(f"{GREEN}All services stopped.{RESET}\n")
    sys.exit(0)

# ── Entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ISP System Launcher")
    parser.add_argument("--check", action="store_true",
                        help="Validate config and dependencies only, then exit")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}{'='*56}{RESET}")
    print(f"{BOLD}{CYAN}   INSTITUTIONAL SNIPER PRO — System Launcher{RESET}")
    print(f"{BOLD}{CYAN}{'='*56}{RESET}\n")

    config_ok = validate_config()

    if args.check:
        print()
        if config_ok:
            print(f"{GREEN}Config check PASSED — ready to launch.{RESET}\n")
        else:
            print(f"{RED}Config check FAILED — fix the errors above before launching.{RESET}\n")
        sys.exit(0 if config_ok else 1)

    if not config_ok:
        print(f"\n{RED}Config validation failed. Fix the errors above.{RESET}")
        print(f"{DIM}Edit .env with your credentials, then re-run.{RESET}\n")
        sys.exit(1)

    # Register Ctrl+C / SIGTERM handler
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    start_services()
    watchdog()
