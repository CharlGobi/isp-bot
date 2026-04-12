"""
ISP Phase 3 — Sentiment Microservice
Flask server that polls Alpha Vantage News Sentiment API, caches results,
and exposes a simple JSON endpoint the MT5 EA queries via WebRequest().

Architecture:
    MT5 EA → WebRequest("http://localhost:5050/sentiment?pair=EURUSD")
           ← {"pair":"EURUSD","score":0.12,"signal":"BULLISH","block":false}

Free API key: https://www.alphavantage.co/support/#api-key
Limit: 25 calls/day on free tier (we cache aggressively to stay within limit)

Install:
    pip install flask requests schedule

Run:
    python isp_sentiment_service.py
    (Keep this running on the same machine/VPS as MT5)
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from flask import Flask, jsonify, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("isp_sentiment.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("ISP.Sentiment")

# ── Config ──────────────────────────────────────────────────────────────────
API_KEY         = os.getenv("ALPHAVANTAGE_KEY", "YOUR_KEY_HERE")
CACHE_TTL_MIN   = 60        # Re-fetch sentiment every 60 minutes
BLOCK_THRESHOLD = -0.10     # Block trade if score below this
BOOST_THRESHOLD =  0.10     # Extra confirmation if score above this
PORT            = 5050

CACHE_PATH = Path("isp_data/sentiment_cache.json")
CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Currency → Ticker topics mapping ────────────────────────────────────────
# Alpha Vantage uses topics; we map forex currencies to relevant equity/topic tickers
CURRENCY_TOPICS = {
    "USD": ["FOREX:USD", "economy_monetary"],
    "EUR": ["FOREX:EUR", "ECONOMY"],
    "GBP": ["FOREX:GBP", "ECONOMY"],
    "JPY": ["FOREX:JPY", "ECONOMY"],
    "XAU": ["COMMODITIES", "FINANCE"],
}

# Pairs and their base/quote currencies
PAIR_CURRENCIES = {
    "EURUSD": ("EUR", "USD"),
    "GBPUSD": ("GBP", "USD"),
    "USDJPY": ("USD", "JPY"),
    "XAUUSD": ("XAU", "USD"),
    "AUDUSD": ("AUD", "USD"),
    "USDCAD": ("USD", "CAD"),
    "USDCHF": ("USD", "CHF"),
    "NZDUSD": ("NZD", "USD"),
}

# ── In-memory cache ──────────────────────────────────────────────────────────
cache: dict = {}
cache_lock = threading.Lock()


def load_cache():
    global cache
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH) as f:
                cache = json.load(f)
            log.info(f"Loaded sentiment cache: {len(cache)} entries")
        except Exception as e:
            log.warning(f"Cache load failed: {e}")
            cache = {}


def save_cache():
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, default=str)


def is_cache_valid(pair: str) -> bool:
    if pair not in cache:
        return False
    ts = datetime.fromisoformat(cache[pair]["fetched_at"])
    return datetime.utcnow() - ts < timedelta(minutes=CACHE_TTL_MIN)


# ── Alpha Vantage API calls ──────────────────────────────────────────────────

def fetch_currency_news_sentiment(currency: str) -> dict:
    """
    Fetch news sentiment from Alpha Vantage for a given currency topic.
    Returns avg sentiment score over last 20 articles.
    """
    if API_KEY == "YOUR_KEY_HERE":
        log.warning("Alpha Vantage API key not set. Using simulated data.")
        return simulate_sentiment(currency)

    # Map currency to search topics
    topics = CURRENCY_TOPICS.get(currency, [])
    if not topics:
        return {"currency": currency, "score": 0.0, "articles": 0}

    # Use the news sentiment endpoint
    url = "https://www.alphavantage.co/query"
    params = {
        "function":    "NEWS_SENTIMENT",
        "topics":      topics[0],
        "apikey":      API_KEY,
        "limit":       50,
        "sort":        "LATEST",
        "time_from":   (datetime.utcnow() - timedelta(hours=24)).strftime("%Y%m%dT%H%M"),
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if "feed" not in data:
            log.warning(f"No feed in response for {currency}: {data.get('Note', data.get('Information', 'Unknown'))}")
            return simulate_sentiment(currency)

        articles = data["feed"]
        if not articles:
            return {"currency": currency, "score": 0.0, "articles": 0}

        # Extract overall sentiment scores
        scores = []
        for article in articles[:20]:
            # Each article has overall_sentiment_score
            try:
                score = float(article.get("overall_sentiment_score", 0))
                scores.append(score)
            except (ValueError, TypeError):
                continue

            # Also check ticker-specific sentiment if available
            for ticker_sent in article.get("ticker_sentiment", []):
                if any(c in ticker_sent.get("ticker", "") for c in ["FOREX", currency]):
                    try:
                        rel_score = float(ticker_sent.get("ticker_sentiment_score", 0))
                        scores.append(rel_score * 1.5)  # Weight ticker-specific higher
                    except (ValueError, TypeError):
                        continue

        avg_score = float(sum(scores) / len(scores)) if scores else 0.0

        log.info(f"AV Sentiment {currency}: {avg_score:.4f} ({len(scores)} data points from {len(articles)} articles)")
        return {
            "currency":  currency,
            "score":     round(avg_score, 4),
            "articles":  len(articles),
            "raw_n":     len(scores),
        }

    except requests.RequestException as e:
        log.error(f"Alpha Vantage request failed for {currency}: {e}")
        return simulate_sentiment(currency)


def simulate_sentiment(currency: str) -> dict:
    """
    Simulated sentiment data for testing without an API key.
    Provides realistic variation based on time of day.
    """
    import random
    import hashlib
    # Deterministic seed based on currency + current hour for consistency
    seed = int(hashlib.md5(f"{currency}{datetime.utcnow().strftime('%Y%m%d%H')}".encode()).hexdigest()[:8], 16)
    random.seed(seed)
    score = round(random.uniform(-0.25, 0.25), 4)
    log.info(f"[SIMULATED] Sentiment {currency}: {score:.4f}")
    return {"currency": currency, "score": score, "articles": 0, "simulated": True}


def compute_pair_sentiment(pair: str) -> dict:
    """
    Compute composite sentiment for a forex pair.
    Base currency bullish + quote currency bearish = bullish pair score.
    """
    currencies = PAIR_CURRENCIES.get(pair.upper())
    if not currencies:
        return {"pair": pair, "score": 0.0, "signal": "NEUTRAL", "block": False, "error": "Unknown pair"}

    base, quote = currencies

    base_data  = fetch_currency_news_sentiment(base)
    quote_data = fetch_currency_news_sentiment(quote)

    base_score  = base_data.get("score",  0.0)
    quote_score = quote_data.get("score", 0.0)

    # Pair score: base bullish vs quote bearish
    pair_score = round(base_score - quote_score, 4)

    if pair_score >= BOOST_THRESHOLD:
        signal = "BULLISH"
    elif pair_score <= -BOOST_THRESHOLD:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    block = pair_score <= BLOCK_THRESHOLD

    result = {
        "pair":        pair,
        "score":       pair_score,
        "base_score":  base_score,
        "quote_score": quote_score,
        "signal":      signal,
        "block":       block,
        "fetched_at":  datetime.utcnow().isoformat(),
        "base_articles": base_data.get("articles", 0),
    }

    log.info(f"Pair sentiment {pair}: {pair_score:.4f} [{signal}] {'BLOCK' if block else 'ALLOW'}")
    return result


def refresh_pair(pair: str):
    """Fetch fresh sentiment and update cache."""
    result = compute_pair_sentiment(pair)
    with cache_lock:
        cache[pair] = result
    save_cache()
    return result


def background_refresh():
    """Background thread: refresh all pairs every CACHE_TTL_MIN minutes."""
    while True:
        for pair in PAIR_CURRENCIES.keys():
            try:
                refresh_pair(pair)
                time.sleep(3)  # Space out API calls to stay within rate limits
            except Exception as e:
                log.error(f"Background refresh failed for {pair}: {e}")
        log.info(f"All pairs refreshed. Next refresh in {CACHE_TTL_MIN} min.")
        time.sleep(CACHE_TTL_MIN * 60)


# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/sentiment", methods=["GET"])
def get_sentiment():
    """
    Main endpoint queried by MT5 EA.
    Query: GET /sentiment?pair=EURUSD
    Response: {"pair":"EURUSD","score":0.12,"signal":"BULLISH","block":false}
    """
    pair = request.args.get("pair", "").upper()

    if not pair:
        return jsonify({"error": "pair parameter required"}), 400

    pair = pair.replace("/", "").replace("-", "").replace("_", "")

    # Serve from cache if valid
    if is_cache_valid(pair):
        with cache_lock:
            return jsonify(cache[pair])

    # Fetch fresh data
    result = refresh_pair(pair)
    return jsonify(result)


@app.route("/sentiment/all", methods=["GET"])
def get_all_sentiment():
    """Dashboard endpoint: returns sentiment for all tracked pairs."""
    results = {}
    with cache_lock:
        for pair in PAIR_CURRENCIES.keys():
            if pair in cache:
                results[pair] = cache[pair]
            else:
                results[pair] = {"pair": pair, "score": 0.0, "signal": "NEUTRAL", "block": False, "stale": True}
    return jsonify(results)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":    "ok",
        "cached":    list(cache.keys()),
        "api_key":   "configured" if API_KEY != "YOUR_KEY_HERE" else "missing",
        "timestamp": datetime.utcnow().isoformat(),
    })


if __name__ == "__main__":
    log.info("=== ISP Sentiment Service Starting ===")
    log.info(f"Port: {PORT} | Cache TTL: {CACHE_TTL_MIN} min | Block threshold: {BLOCK_THRESHOLD}")
    log.info(f"API Key: {'SET' if API_KEY != 'YOUR_KEY_HERE' else 'NOT SET — using simulated data'}")

    load_cache()

    # Start background refresh thread
    bg = threading.Thread(target=background_refresh, daemon=True)
    bg.start()
    log.info("Background sentiment refresh thread started.")

    # Run Flask server
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
