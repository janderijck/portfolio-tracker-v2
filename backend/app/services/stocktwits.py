"""
StockTwits sentiment service.

Fetches social sentiment data from the free StockTwits API.
No authentication required.
"""
import time
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

STOCKTWITS_API_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
SENTIMENT_CACHE_TTL = 1800  # 30 minutes

_sentiment_cache: dict = {}  # {ticker: {'data': ..., 'timestamp': float}}


def _normalize_ticker(ticker: str) -> list[str]:
    """
    Generate StockTwits-compatible ticker variants.

    StockTwits uses US-style tickers without exchange suffixes.
    E.g. ENGI.PA -> try ['ENGI.PA', 'ENGI'], AAPL -> ['AAPL']
    """
    candidates = [ticker]
    if '.' in ticker:
        base = ticker.split('.')[0]
        if base not in candidates:
            candidates.append(base)
    return candidates


def _fetch_sentiment(symbol: str) -> Optional[requests.Response]:
    """Try fetching sentiment for a single symbol."""
    resp = requests.get(
        STOCKTWITS_API_URL.format(symbol=symbol),
        timeout=10,
        headers={"User-Agent": "PortfolioTracker/1.0"},
    )
    if resp.status_code == 200:
        return resp
    return None


def get_sentiment(ticker: str) -> Optional[dict]:
    """
    Get sentiment summary for a ticker from StockTwits.

    Tries the original ticker first, then stripped variants
    (e.g. ENGI.PA -> ENGI) since StockTwits mainly supports US tickers.

    Returns dict with bullish/bearish counts and percentage,
    or None if unavailable.
    """
    cached = _sentiment_cache.get(ticker)
    if cached and (time.time() - cached['timestamp']) < SENTIMENT_CACHE_TTL:
        return cached['data']

    try:
        resp = None
        for candidate in _normalize_ticker(ticker):
            resp = _fetch_sentiment(candidate)
            if resp:
                break

        if not resp:
            # Cache the miss too to avoid repeated API calls
            _sentiment_cache[ticker] = {'data': None, 'timestamp': time.time()}
            return None

        data = resp.json()
        messages = data.get("messages", [])
        if not messages:
            return None

        bullish = 0
        bearish = 0
        for msg in messages:
            sentiment = None
            entities = msg.get("entities")
            if entities and isinstance(entities, dict):
                s = entities.get("sentiment")
                if s and isinstance(s, dict):
                    sentiment = s.get("basic")

            if sentiment == "Bullish":
                bullish += 1
            elif sentiment == "Bearish":
                bearish += 1

        total = bullish + bearish
        if total == 0:
            return None

        result = {
            "bullish": bullish,
            "bearish": bearish,
            "total": total,
            "bullish_percent": round((bullish / total) * 100, 1),
            "message_count": len(messages),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        _sentiment_cache[ticker] = {'data': result, 'timestamp': time.time()}
        return result

    except requests.RequestException as e:
        logger.warning("StockTwits request failed for %s: %s", ticker, e)
        return None
    except (ValueError, KeyError) as e:
        logger.warning("StockTwits parse error for %s: %s", ticker, e)
        return None
