"""
Morningstar API client for fetching fund NAV prices, history, and dividend data.

Used for Belgian/European mutual funds (like Plato Institutional Index Fund World)
that are not available on Yahoo Finance or Finnhub.

Uses public Morningstar endpoints (no authentication required):
- SecuritySearch.ashx for fund lookup by ISIN
- tools.morningstar.co.uk screener for current NAV
- tools.morningstar.co.uk timeseries for historical prices
"""
import json
import logging
import requests
from typing import Optional, List
from datetime import datetime, timedelta

from .database import get_db, get_figi_cache, save_figi_cache, get_cached_price, save_price_to_cache

logger = logging.getLogger(__name__)

_MS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Accept': 'application/json',
}

# Universe IDs to search (Belgian funds, European funds, European ETFs)
_UNIVERSE_IDS = ['FOBEL$$ALL', 'FOEUR$$ALL', 'ETEUR$$ALL']


# --- SecId cache helpers ---
def _get_cached_fund_info(isin: str) -> Optional[dict]:
    """Get cached Morningstar fund info for an ISIN.

    Returns dict with 'sec_id' and 'name', or None.
    """
    with get_db() as conn:
        cached = get_figi_cache(conn, 'morningstar_isin', isin)
        if cached and cached[0].get('ticker'):
            return {
                'sec_id': cached[0]['ticker'],
                'name': cached[0].get('name', ''),
                'universe': cached[0].get('exch_code', 'FOBEL$$ALL'),
            }
    return None


def _save_fund_info_cache(isin: str, sec_id: str, name: str = '', universe: str = 'FOBEL$$ALL'):
    """Cache ISIN -> fund info mapping."""
    with get_db() as conn:
        save_figi_cache(conn, 'morningstar_isin', isin, [{
            'ticker': sec_id,
            'name': name,
            'exch_code': universe,
            'security_type': 'FUND',
            'market_sector': '',
        }])


# --- Fund lookup via SecuritySearch ---
def _search_fund_via_autocomplete(isin: str) -> Optional[dict]:
    """
    Search for a fund via Morningstar SecuritySearch.ashx (autocomplete endpoint).

    This endpoint is public and returns fund metadata including:
    - i: Fund ID (SecId, e.g. F0000196QU)
    - pi: Performance ID (e.g. 0P0001MTOA)
    - n: Fund name
    - t: Type (2 = fund)

    Returns dict with sec_id, name or None.
    """
    for site in ['be', 'co.uk']:
        try:
            resp = requests.get(
                f'https://www.morningstar.{site}/{site.replace("co.uk", "uk").replace("be", "be")}/util/SecuritySearch.ashx',
                params={
                    'q': isin,
                    'preferedList': '',
                    'source': 'nav',
                    'moduleId': 6,
                    'if498': 'true',
                },
                headers={'User-Agent': _MS_HEADERS['User-Agent']},
                timeout=15,
            )
            if resp.status_code != 200 or not resp.text.strip():
                continue

            # Parse pipe-delimited response
            for line in resp.text.strip().split('\n'):
                parts = line.strip().split('|')
                if len(parts) > 1 and parts[1]:
                    try:
                        data = json.loads(parts[1])
                        sec_id = data.get('i', '')
                        name = data.get('n', '')
                        if sec_id:
                            logger.info(f"Morningstar: found fund {name} ({isin}) via SecuritySearch, SecId={sec_id}")
                            return {'sec_id': sec_id, 'name': name}
                    except (json.JSONDecodeError, KeyError):
                        continue

        except Exception as e:
            logger.debug(f"Morningstar: SecuritySearch error on {site}: {e}")
            continue

    return None


def search_fund_by_isin(isin: str) -> Optional[dict]:
    """
    Search for a fund on Morningstar via ISIN.

    Strategy:
    1. Check cache
    2. Use public screener (tools.morningstar.co.uk) for NAV + metadata
    3. Fallback to SecuritySearch.ashx for fund ID, then screener for NAV

    Returns:
        Dict with name, current_price, currency, sec_id, close_date or None
    """
    # Check cache first
    cached = _get_cached_fund_info(isin)

    # Try public screener endpoint (gets NAV + metadata in one call)
    for universe in _UNIVERSE_IDS:
        try:
            resp = requests.get(
                'https://tools.morningstar.co.uk/api/rest.svc/9vehuxllxs/security/screener',
                params={
                    'outputType': 'json',
                    'version': '1',
                    'languageId': 'en-GB',
                    'securityDataPoints': 'SecId|Name|ClosePrice|ClosePriceDate|PriceCurrency|ISIN',
                    'filters': f'ISIN:IN:{isin}',
                    'universeIds': universe,
                },
                headers=_MS_HEADERS,
                timeout=15,
            )
            if resp.status_code != 200:
                continue

            data = resp.json()
            rows = data.get('rows', [])
            if rows:
                row = rows[0]
                sec_id = row.get('SecId', '')
                name = row.get('Name', '')
                close_price = row.get('ClosePrice')
                currency = row.get('PriceCurrency', 'EUR')
                close_date = row.get('ClosePriceDate', '')

                # Cache fund info
                if sec_id:
                    _save_fund_info_cache(isin, sec_id, name, universe)

                result = {
                    'name': name,
                    'current_price': float(close_price) if close_price is not None else None,
                    'currency': currency,
                    'sec_id': sec_id,
                    'close_date': close_date,
                }
                logger.info(f"Morningstar: found fund {name} ({isin}) - NAV {close_price} {currency}")
                return result

        except Exception as e:
            logger.debug(f"Morningstar: screener error for {isin} in {universe}: {e}")
            continue

    # Fallback: use SecuritySearch to find fund ID
    if not cached:
        search_result = _search_fund_via_autocomplete(isin)
        if search_result:
            _save_fund_info_cache(isin, search_result['sec_id'], search_result['name'])
            return {
                'name': search_result['name'],
                'current_price': None,
                'currency': 'EUR',
                'sec_id': search_result['sec_id'],
                'close_date': '',
            }

    logger.info(f"Morningstar: no fund found for ISIN {isin}")
    return None


# --- Current NAV ---
FUND_PRICE_CACHE_TTL = 86400  # 24 hours - NAV updates once per day


def get_fund_nav(isin: str) -> Optional[dict]:
    """
    Get current NAV for a fund via ISIN.

    1. Check price_cache (24h TTL)
    2. Call Morningstar public screener
    3. Cache result

    Returns:
        Dict with current_price, change_percent, currency or None
    """
    # Check price cache (use ISIN as cache key)
    with get_db() as conn:
        cached = get_cached_price(conn, isin)
        if cached and cached.get('updated_at'):
            cache_age = (datetime.now() - datetime.fromisoformat(cached['updated_at'])).total_seconds()
            if cache_age < FUND_PRICE_CACHE_TTL:
                return {
                    'current_price': cached['current_price'],
                    'change_percent': cached['change_percent'],
                    'currency': cached['currency'],
                }

    # Fetch from Morningstar
    ms_result = search_fund_by_isin(isin)
    if not ms_result or ms_result.get('current_price') is None:
        return None

    result = {
        'current_price': ms_result['current_price'],
        'change_percent': 0,  # Morningstar screener doesn't return daily change
        'currency': ms_result['currency'],
    }

    # Cache the result
    with get_db() as conn:
        save_price_to_cache(
            conn, isin,
            result['current_price'],
            result['change_percent'],
            result['currency'],
        )

    return result


# --- Historical NAV (for charts) ---
def get_fund_nav_history(isin: str, period: str = '1y') -> List[dict]:
    """
    Get historical NAV for charts.

    Uses the public Morningstar timeseries endpoint (no auth required).
    The timeseries ID format is: {secId}]2]1]{universe}

    Args:
        isin: Fund ISIN
        period: Time period (1mo, 3mo, 6mo, 1y, 2y, 5y, max)

    Returns:
        List of {date: str, price: float}
    """
    # Get fund info (from cache or API)
    fund_info = _get_cached_fund_info(isin)
    if not fund_info:
        ms_result = search_fund_by_isin(isin)
        if not ms_result or not ms_result.get('sec_id'):
            return []
        fund_info = _get_cached_fund_info(isin)
        if not fund_info:
            return []

    sec_id = fund_info['sec_id']
    universe = fund_info.get('universe', 'FOBEL$$ALL')

    # Build timeseries ID: {secId}]2]1]{universe}
    timeseries_id = f'{sec_id}]2]1]{universe}'

    # Map period to start date
    period_days = {
        '1d': 1, '5d': 5,
        '1mo': 30, '3mo': 90, '6mo': 180,
        '1y': 365, '2y': 730, '5y': 1825,
        '10y': 3650, 'ytd': (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
        'max': 3650,
    }
    days = period_days.get(period, 365)
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    try:
        resp = requests.get(
            'https://tools.morningstar.co.uk/api/rest.svc/timeseries_price/t92wz0sj7c',
            params={
                'currencyId': 'EUR',
                'idtype': 'Morningstar',
                'frequency': 'daily',
                'outputType': 'JSON',
                'startDate': start_date,
                'id': timeseries_id,
            },
            headers=_MS_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        # Parse the timeseries response
        history = []
        time_series = data.get('TimeSeries', {})
        securities = time_series.get('Security', [])

        if not securities:
            return []

        # Can be a single object or list
        security = securities[0] if isinstance(securities, list) else securities
        history_details = security.get('HistoryDetail', [])

        for point in history_details:
            end_date = point.get('EndDate', '')
            value = point.get('Value', '')
            if end_date and value:
                try:
                    history.append({
                        'date': end_date,
                        'price': float(value),
                    })
                except (ValueError, TypeError):
                    continue

        logger.info(f"Morningstar: fetched {len(history)} history points for {isin}")
        return history

    except Exception as e:
        logger.warning(f"Morningstar: history error for {isin}: {e}")
        return []
