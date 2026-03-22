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


def get_sentiment(ticker: str) -> Optional[dict]:
    """
    Get sentiment summary for a ticker from StockTwits.

    Returns dict with bullish/bearish counts and percentage,
    or None if unavailable.
    """
    cached = _sentiment_cache.get(ticker)
    if cached and (time.time() - cached['timestamp']) < SENTIMENT_CACHE_TTL:
        return cached['data']

    try:
        resp = requests.get(
            STOCKTWITS_API_URL.format(symbol=ticker),
            timeout=10,
            headers={"User-Agent": "PortfolioTracker/1.0"},
        )
        if resp.status_code != 200:
            logger.warning("StockTwits returned %d for %s", resp.status_code, ticker)
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
