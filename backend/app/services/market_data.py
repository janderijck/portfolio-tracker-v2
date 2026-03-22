"""
Market data service for fetching prices and exchange rates from Yahoo Finance, Finnhub and OpenFIGI.
"""
import logging
import time as _time
import yfinance as yf
import finnhub
import requests
from typing import Optional, List
from datetime import datetime, date

logger = logging.getLogger(__name__)
from .database import (
    get_db, get_cached_exchange_rate, save_exchange_rate_to_cache,
    get_user_settings, get_cached_price, save_price_to_cache,
    get_figi_cache, save_figi_cache,
)

PRICE_CACHE_TTL = 3600  # 1 hour in seconds
DIVIDEND_INFO_CACHE_TTL = 86400  # 24 hours in seconds
PERIOD_CHANGES_CACHE_TTL = 900  # 15 minutes in seconds

_dividend_info_cache: dict = {}  # {ticker: {'data': ..., 'timestamp': float}}
_period_changes_cache: dict = {}  # {cache_key: {'data': ..., 'timestamp': float}}

OPENFIGI_API_URL = "https://api.openfigi.com/v3"

OPENFIGI_EXCH_TO_YAHOO = {
    'BB': '.BR', 'NA': '.AS', 'FP': '.PA',
    'GY': '.DE', 'GR': '.DE', 'IM': '.MI',
    'LN': '.L',  'SW': '.SW', 'SM': '.MC',
    'ID': '.IR', 'FH': '.HE', 'AV': '.VI',
    'DC': '.CO', 'SS': '.ST', 'NO': '.OL',
    'PL': '.LS', 'AU': '.AX', 'CT': '.TO',
    'US': '', 'UN': '', 'UQ': '', 'UW': '', 'UP': '',
}

EXCH_CODE_TO_CURRENCY = {
    'BB': 'EUR', 'NA': 'EUR', 'FP': 'EUR', 'GY': 'EUR', 'GR': 'EUR',
    'IM': 'EUR', 'SM': 'EUR', 'FH': 'EUR', 'AV': 'EUR', 'PL': 'EUR',
    'LN': 'GBP', 'SW': 'CHF', 'DC': 'DKK', 'SS': 'SEK', 'NO': 'NOK',
    'ID': 'EUR', 'AU': 'AUD', 'CT': 'CAD',
    'US': 'USD', 'UN': 'USD', 'UQ': 'USD', 'UW': 'USD', 'UP': 'USD',
}

EXCH_CODE_TO_COUNTRY = {
    'BB': 'België', 'NA': 'Nederland', 'FP': 'Frankrijk',
    'GY': 'Duitsland', 'GR': 'Duitsland', 'IM': 'Italië',
    'LN': 'Verenigd Koninkrijk', 'SW': 'Zwitserland', 'SM': 'Spanje',
    'ID': 'Ierland', 'FH': 'Finland', 'AV': 'Oostenrijk',
    'DC': 'Denemarken', 'SS': 'Zweden', 'NO': 'Noorwegen',
    'PL': 'Portugal', 'AU': 'Australië', 'CT': 'Canada',
    'US': 'Verenigde Staten', 'UN': 'Verenigde Staten',
    'UQ': 'Verenigde Staten', 'UW': 'Verenigde Staten', 'UP': 'Verenigde Staten',
}

# EUR exchanges to prefer for European ISINs
EUR_EXCH_CODES = {'BB', 'NA', 'FP', 'GY', 'GR', 'IM'}


def _get_openfigi_api_key() -> Optional[str]:
    """Get optional OpenFIGI API key from user settings."""
    try:
        with get_db() as conn:
            settings = get_user_settings(conn)
            return settings.get('openfigi_api_key')
    except Exception:
        return None


def _openfigi_headers() -> dict:
    """Build request headers for OpenFIGI API."""
    headers = {"Content-Type": "text/json"}
    api_key = _get_openfigi_api_key()
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key
    return headers


def _figi_result_to_dict(item: dict) -> Optional[dict]:
    """Convert a single OpenFIGI data item to our standard format."""
    ticker = item.get('ticker')
    exch_code = item.get('exchCode', '')

    if not ticker:
        return None

    # Only return results with known exchange codes
    if exch_code not in OPENFIGI_EXCH_TO_YAHOO:
        return None

    yahoo_suffix = OPENFIGI_EXCH_TO_YAHOO[exch_code]
    yahoo_ticker = f"{ticker}{yahoo_suffix}"

    return {
        'ticker': ticker,
        'yahoo_ticker': yahoo_ticker,
        'name': item.get('name', ''),
        'exch_code': exch_code,
        'currency': EXCH_CODE_TO_CURRENCY.get(exch_code, 'USD'),
        'country': EXCH_CODE_TO_COUNTRY.get(exch_code, 'Onbekend'),
        'security_type': item.get('securityType', ''),
        'market_sector': item.get('marketSector', ''),
    }


def openfigi_map_isin(isin: str) -> list:
    """
    Map an ISIN to ticker(s) via OpenFIGI API.
    Returns list of dicts with ticker, yahoo_ticker, name, exch_code, etc.
    """
    # Check cache first
    # NOTE: cached 'ticker' field stores the full yahoo_ticker (with suffix already applied)
    with get_db() as conn:
        cached = get_figi_cache(conn, 'isin', isin)
        if cached:
            results = []
            for c in cached:
                yahoo_ticker = c['ticker']  # already contains suffix
                results.append({
                    'ticker': yahoo_ticker,
                    'yahoo_ticker': yahoo_ticker,
                    'name': c['name'] or '',
                    'exch_code': c['exch_code'] or '',
                    'currency': EXCH_CODE_TO_CURRENCY.get(c['exch_code'] or '', 'USD'),
                    'country': EXCH_CODE_TO_COUNTRY.get(c['exch_code'] or '', 'Onbekend'),
                    'security_type': c['security_type'] or '',
                    'market_sector': c['market_sector'] or '',
                })
            return results

    try:
        resp = requests.post(
            f"{OPENFIGI_API_URL}/mapping",
            headers=_openfigi_headers(),
            json=[{"idType": "ID_ISIN", "idValue": isin}],
            timeout=10,
        )

        if resp.status_code == 429:
            logger.warning(f"OpenFIGI rate limited for ISIN {isin}")
            return []

        if resp.status_code != 200:
            logger.warning(f"OpenFIGI error {resp.status_code} for ISIN {isin}")
            return []

        data = resp.json()
        if not data or not isinstance(data, list) or 'data' not in data[0]:
            return []

        results = []
        seen = set()
        for item in data[0]['data']:
            converted = _figi_result_to_dict(item)
            if converted and converted['yahoo_ticker'] not in seen:
                seen.add(converted['yahoo_ticker'])
                results.append(converted)

        # Cache results
        if results:
            cache_entries = [{
                'ticker': r['yahoo_ticker'],
                'name': r['name'],
                'exch_code': r['exch_code'],
                'security_type': r['security_type'],
                'market_sector': r['market_sector'],
            } for r in results]
            with get_db() as conn:
                save_figi_cache(conn, 'isin', isin, cache_entries)

        return results

    except requests.RequestException as e:
        logger.error(f"OpenFIGI request error for ISIN {isin}: {e}")
        return []


def openfigi_search(query: str) -> list:
    """
    Search for securities by name/ticker via OpenFIGI API.
    Returns list of dicts with ticker, yahoo_ticker, name, exch_code, etc.
    """
    query_lower = query.lower()

    # Check cache first
    # NOTE: cached 'ticker' field stores the full yahoo_ticker (with suffix already applied)
    with get_db() as conn:
        cached = get_figi_cache(conn, 'search', query_lower)
        if cached:
            results = []
            for c in cached:
                yahoo_ticker = c['ticker']  # already contains suffix
                results.append({
                    'ticker': yahoo_ticker,
                    'yahoo_ticker': yahoo_ticker,
                    'name': c['name'] or '',
                    'exch_code': c['exch_code'] or '',
                    'currency': EXCH_CODE_TO_CURRENCY.get(c['exch_code'] or '', 'USD'),
                    'country': EXCH_CODE_TO_COUNTRY.get(c['exch_code'] or '', 'Onbekend'),
                    'security_type': c['security_type'] or '',
                    'market_sector': c['market_sector'] or '',
                })
            return results

    try:
        resp = requests.post(
            f"{OPENFIGI_API_URL}/search",
            headers=_openfigi_headers(),
            json={"query": query, "marketSecDes": "Equity"},
            timeout=10,
        )

        if resp.status_code == 429:
            logger.warning(f"OpenFIGI rate limited for search '{query}'")
            return []

        if resp.status_code != 200:
            logger.warning(f"OpenFIGI error {resp.status_code} for search '{query}'")
            return []

        data = resp.json()
        if not data or 'data' not in data:
            return []

        # 1. Scan ALL results, filter on known exchanges + Common Stock/ETP/REIT
        all_results = []
        for item in data['data']:
            sec_type = item.get('securityType', '')
            if sec_type not in ('Common Stock', 'ETP', 'REIT'):
                continue
            converted = _figi_result_to_dict(item)
            if converted:
                all_results.append(converted)

        # 2. Deduplicate on yahoo_ticker
        seen = set()
        unique_results = []
        for r in all_results:
            if r['yahoo_ticker'] not in seen:
                seen.add(r['yahoo_ticker'])
                unique_results.append(r)

        # 3. Sort: EUR exchanges first, then US, then rest
        def sort_key(r):
            if r['exch_code'] in EUR_EXCH_CODES:
                return 0
            if r['exch_code'] in ('US', 'UN', 'UQ', 'UW', 'UP'):
                return 1
            return 2

        unique_results.sort(key=sort_key)

        # 4. Max 10 results
        results = unique_results[:10]

        # Cache results
        if results:
            cache_entries = [{
                'ticker': r['yahoo_ticker'],
                'name': r['name'],
                'exch_code': r['exch_code'],
                'security_type': r['security_type'],
                'market_sector': r['market_sector'],
            } for r in results]
            with get_db() as conn:
                save_figi_cache(conn, 'search', query_lower, cache_entries)

        return results

    except requests.RequestException as e:
        logger.error(f"OpenFIGI request error for search '{query}': {e}")
        return []


def _get_cached_price_if_fresh(ticker: str) -> Optional[dict]:
    """Return cached price if it exists and is less than PRICE_CACHE_TTL old."""
    with get_db() as conn:
        cached = get_cached_price(conn, ticker)
        if cached and cached.get('updated_at'):
            cache_age = (datetime.now() - datetime.fromisoformat(cached['updated_at'])).total_seconds()
            if cache_age < PRICE_CACHE_TTL:
                return {
                    'current_price': cached['current_price'],
                    'change_percent': cached['change_percent'],
                    'currency': cached['currency'],
                }
    return None


def _save_price_result(ticker: str, result: dict):
    """Save a price result to cache."""
    with get_db() as conn:
        save_price_to_cache(
            conn, ticker,
            result['current_price'],
            result['change_percent'],
            result['currency'],
        )


def get_current_price(ticker: str) -> Optional[dict]:
    """
    Fetch current price from Yahoo Finance, with Finnhub as fallback.
    Results are cached for 1 hour to avoid overloading external APIs.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with current_price, change_percent, currency or None if unavailable
    """
    # Check cache first
    cached = _get_cached_price_if_fresh(ticker)
    if cached:
        return cached

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='5d')

        if hist.empty:
            # Try Finnhub as fallback
            return get_current_price_finnhub(ticker)

        current_price = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
        change_percent = ((current_price - prev_close) / prev_close) * 100 if prev_close else 0

        info = stock.info
        currency = info.get('currency', 'USD')

        result = {
            'current_price': current_price,
            'change_percent': change_percent,
            'currency': currency
        }
        _save_price_result(ticker, result)
        return result
    except Exception:
        # Try Finnhub as fallback
        return get_current_price_finnhub(ticker)


def get_exchange_rate(from_currency: str = 'USD', to_currency: str = 'EUR') -> float:
    """
    Get exchange rate from Yahoo Finance with caching.

    Args:
        from_currency: Source currency code
        to_currency: Target currency code

    Returns:
        Exchange rate, or 1.0 if unavailable
    """
    if from_currency == to_currency:
        return 1.0

    # Check cache first
    with get_db() as conn:
        cached = get_cached_exchange_rate(conn, from_currency, to_currency)
        if cached:
            return cached

    # Fetch from Yahoo Finance
    try:
        ticker_symbol = f"{from_currency}{to_currency}=X"
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period="1d")

        if not data.empty:
            rate = float(data['Close'].iloc[-1])
        else:
            # Try inverse
            ticker_symbol = f"{to_currency}{from_currency}=X"
            ticker = yf.Ticker(ticker_symbol)
            data = ticker.history(period="1d")
            if not data.empty:
                rate = 1 / float(data['Close'].iloc[-1])
            else:
                rate = 1.0

        # Cache the rate
        with get_db() as conn:
            save_exchange_rate_to_cache(conn, from_currency, to_currency, rate)

        return rate
    except Exception:
        return 1.0


def lookup_by_isin(isin: str) -> Optional[dict]:
    """
    Lookup stock information by ISIN.

    Resolution order:
    1. OpenFIGI (single API call for exact ticker mapping)
    2. Yahoo Finance with the resolved ticker
    3. Finnhub as fallback for European ISINs
    4. Yahoo Finance with ISIN directly as last resort

    Args:
        isin: International Securities Identification Number

    Returns:
        Dict with ticker, name, currency, country, etc. or None if not found
    """
    european_prefixes = ['AT', 'BE', 'CY', 'DE', 'ES', 'FI', 'FR', 'GB', 'GR', 'IE', 'IT', 'LU', 'NL', 'PT']
    is_european = any(isin.startswith(prefix) for prefix in european_prefixes)

    # 1. Try OpenFIGI first
    figi_results = openfigi_map_isin(isin)
    if figi_results:
        # For European ISINs, prefer EUR exchanges
        if is_european:
            eur_results = [r for r in figi_results if r['exch_code'] in EUR_EXCH_CODES]
            if eur_results:
                figi_results = eur_results + [r for r in figi_results if r['exch_code'] not in EUR_EXCH_CODES]

        # Try Yahoo Finance with the best OpenFIGI ticker
        for figi in figi_results:
            yahoo_ticker = figi['yahoo_ticker']
            try:
                stock = yf.Ticker(yahoo_ticker)
                hist = stock.history(period='5d')
                if not hist.empty:
                    info = stock.info
                    current_price = float(hist['Close'].iloc[-1])
                    name = info.get('longName') or info.get('shortName') or figi['name']
                    currency = info.get('currency') or figi['currency']
                    country = info.get('country', figi['country'])

                    country_map = {
                        'United States': 'Verenigde Staten',
                        'Netherlands': 'Nederland',
                        'Germany': 'Duitsland',
                        'France': 'Frankrijk',
                        'United Kingdom': 'Verenigd Koninkrijk',
                        'Belgium': 'België',
                    }
                    country = country_map.get(country, country)

                    sector = info.get('sector', '')
                    asset_type = 'REIT' if 'REIT' in sector or 'Real Estate' in sector else 'STOCK'
                    dividend_yield = info.get('dividendYield') or info.get('trailingAnnualDividendYield')
                    pays_dividend = dividend_yield is not None and dividend_yield > 0

                    return {
                        'ticker': yahoo_ticker,
                        'isin': isin,
                        'name': name,
                        'currency': currency,
                        'country': country,
                        'asset_type': asset_type,
                        'current_price': current_price,
                        'yahoo_ticker': yahoo_ticker,
                        'pays_dividend': pays_dividend,
                        'dividend_yield': dividend_yield,
                    }
            except Exception:
                continue

    # 2. Finnhub fallback for European ISINs
    if is_european:
        result = lookup_by_isin_finnhub(isin)
        if result:
            return result

    # 3. Morningstar for funds (Belgian/European mutual funds)
    # Try before Yahoo ISIN-direct lookup to properly identify funds
    try:
        from .morningstar import search_fund_by_isin
        ms_result = search_fund_by_isin(isin)
        if ms_result:
            return {
                'ticker': isin,           # Use ISIN as ticker for funds
                'isin': isin,
                'name': ms_result['name'],
                'currency': ms_result['currency'],
                'country': 'België',
                'asset_type': 'FUND',
                'current_price': ms_result.get('current_price'),
                'yahoo_ticker': None,
                'pays_dividend': True,    # Distribution funds
                'dividend_yield': None,
            }
    except Exception as e:
        logger.warning(f"Morningstar lookup failed for ISIN {isin}: {e}")

    # 4. Yahoo Finance with ISIN directly as last resort
    try:
        stock = yf.Ticker(isin)
        info = stock.info

        if info and info.get('symbol'):
            ticker = info.get('symbol', '')
            hist = stock.history(period='5d')

            if hist.empty:
                return None

            name = info.get('longName') or info.get('shortName', '')
            currency = info.get('currency', 'USD')
            country = info.get('country', 'Verenigde Staten')

            country_map = {
                'United States': 'Verenigde Staten',
                'Netherlands': 'Nederland',
                'Germany': 'Duitsland',
                'France': 'Frankrijk',
                'United Kingdom': 'Verenigd Koninkrijk',
                'Belgium': 'België',
            }
            country = country_map.get(country, country)

            sector = info.get('sector', '')
            asset_type = 'REIT' if 'REIT' in sector or 'Real Estate' in sector else 'STOCK'
            current_price = float(hist['Close'].iloc[-1])
            dividend_yield = info.get('dividendYield') or info.get('trailingAnnualDividendYield')
            pays_dividend = dividend_yield is not None and dividend_yield > 0

            return {
                'ticker': ticker,
                'isin': isin,
                'name': name,
                'currency': currency,
                'country': country,
                'asset_type': asset_type,
                'current_price': current_price,
                'yahoo_ticker': ticker,
                'pays_dividend': pays_dividend,
                'dividend_yield': dividend_yield,
            }
    except Exception as e:
        logger.error(f"Error looking up ISIN {isin}: {e}")

    # 5. Finnhub fallback for non-European ISINs
    if not is_european:
        result = lookup_by_isin_finnhub(isin)
        if result:
            return result

    return None


def resolve_yahoo_ticker_from_isin(isin: str) -> Optional[str]:
    """
    Resolve an ISIN to the best yahoo_ticker via OpenFIGI.
    Prefers EUR exchanges for European ISINs.

    Returns:
        Yahoo ticker string (e.g. "ENGI.PA") or None if not found.
    """
    if not isin:
        return None

    european_prefixes = ['AT', 'BE', 'CY', 'DE', 'ES', 'FI', 'FR', 'GB', 'GR', 'IE', 'IT', 'LU', 'NL', 'PT']
    is_european = any(isin.startswith(prefix) for prefix in european_prefixes)

    results = openfigi_map_isin(isin)
    if not results:
        return None

    # For European ISINs, prefer EUR exchanges
    if is_european:
        eur_results = [r for r in results if r['exch_code'] in EUR_EXCH_CODES]
        if eur_results:
            return eur_results[0]['yahoo_ticker']

    return results[0]['yahoo_ticker']


def _get_finnhub_client() -> Optional[finnhub.Client]:
    """Get Finnhub client if API key is configured."""
    try:
        with get_db() as conn:
            settings = get_user_settings(conn)
            api_key = settings.get('finnhub_api_key')
            if api_key:
                return finnhub.Client(api_key=api_key)
    except Exception:
        pass
    return None


def lookup_by_isin_finnhub(isin: str) -> Optional[dict]:
    """
    Lookup stock information by ISIN using Finnhub.

    Finnhub supports European ISINs better than Yahoo Finance.

    Args:
        isin: International Securities Identification Number

    Returns:
        Dict with ticker, name, currency, country, etc. or None if not found
    """
    client = _get_finnhub_client()
    if not client:
        return None

    try:
        # Search by ISIN
        result = client.symbol_lookup(isin)

        if not result or 'result' not in result or len(result['result']) == 0:
            return None

        # Get first result
        first = result['result'][0]
        symbol = first.get('symbol')

        if not symbol:
            return None

        # Get detailed quote
        quote = client.quote(symbol)

        # Get profile for more details
        profile = client.company_profile2(symbol=symbol)

        name = first.get('description', '')
        if profile and profile.get('name'):
            name = profile['name']

        # Determine currency from exchange
        exchange = first.get('displaySymbol', '').split(':')[0] if ':' in first.get('displaySymbol', '') else ''
        currency_map = {
            'BR': 'EUR',  # Brussels
            'AS': 'EUR',  # Amsterdam
            'PA': 'EUR',  # Paris
            'DE': 'EUR',  # Germany (XETRA)
            'MI': 'EUR',  # Milan
            'L': 'GBP',   # London
            'SW': 'CHF',  # Swiss
        }
        currency = currency_map.get(exchange, profile.get('currency', 'EUR') if profile else 'EUR')

        # Map country
        country = profile.get('country', 'Onbekend') if profile else 'Onbekend'
        country_map = {
            'US': 'Verenigde Staten',
            'NL': 'Nederland',
            'DE': 'Duitsland',
            'FR': 'Frankrijk',
            'GB': 'Verenigd Koninkrijk',
            'BE': 'België',
        }
        country = country_map.get(country, country)

        # Get current price
        current_price = quote.get('c') if quote else None

        return {
            'ticker': symbol,
            'isin': isin,
            'name': name,
            'currency': currency,
            'country': country,
            'asset_type': 'STOCK',
            'current_price': current_price,
            'yahoo_ticker': None,
            'pays_dividend': False,
            'dividend_yield': None
        }

    except Exception as e:
        logger.error(f"Error looking up ISIN {isin} via Finnhub: {e}")
        return None


def get_current_price_finnhub(ticker: str) -> Optional[dict]:
    """
    Fetch current price from Finnhub.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with current_price, change_percent, currency or None if unavailable
    """
    client = _get_finnhub_client()
    if not client:
        return None

    try:
        quote = client.quote(ticker)

        if not quote or quote.get('c') == 0:
            return None

        current_price = quote.get('c')
        prev_close = quote.get('pc')
        change_percent = quote.get('dp', 0)

        # Get profile for currency
        profile = client.company_profile2(symbol=ticker)
        currency = profile.get('currency', 'EUR') if profile else 'EUR'

        result = {
            'current_price': current_price,
            'change_percent': change_percent,
            'currency': currency
        }
        _save_price_result(ticker, result)
        return result

    except Exception as e:
        logger.error(f"Error fetching price for {ticker} via Finnhub: {e}")
        return None


FUND_PRICE_CACHE_TTL = 86400  # 24 hours - NAV updates once per day


def get_fund_price(ticker: str, isin: str) -> Optional[dict]:
    """
    Get price for funds (FUND asset type) via Morningstar.

    1. Check price_cache (24h TTL)
    2. Morningstar API via morningstar.get_fund_nav(isin)
    3. Return None (caller falls back to manual prices)
    """
    from .morningstar import get_fund_nav

    # Check cache first (using ISIN as key, matching morningstar.py)
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

    # Try Morningstar
    result = get_fund_nav(isin)
    if result:
        return result

    return None


def get_cached_price_only(ticker: str) -> Optional[dict]:
    """Return cached price regardless of age. Never fetches from external APIs."""
    with get_db() as conn:
        cached = get_cached_price(conn, ticker)
        if cached and cached.get('current_price') is not None:
            return {
                'current_price': cached['current_price'],
                'change_percent': cached['change_percent'],
                'currency': cached['currency'],
                'updated_at': cached.get('updated_at'),
            }
    return None


def get_historical_monthly_prices(yahoo_tickers: dict, start_date: str) -> dict:
    """
    Fetch historical monthly closing prices for multiple tickers via yfinance.

    Args:
        yahoo_tickers: {internal_ticker: yahoo_ticker_symbol}
        start_date: YYYY-MM-DD format

    Returns:
        {internal_ticker: {YYYY-MM: close_price_in_original_currency}}
    """
    if not yahoo_tickers:
        return {}

    result = {}
    # Build reverse map: yahoo_symbol -> internal_ticker
    reverse_map = {}
    symbols = []
    for internal, yahoo_sym in yahoo_tickers.items():
        reverse_map[yahoo_sym] = internal
        symbols.append(yahoo_sym)
        result[internal] = {}

    try:
        # Batch download monthly data for all tickers at once
        data = yf.download(
            symbols,
            start=start_date,
            interval="1mo",
            auto_adjust=True,
            progress=False,
        )

        if data.empty:
            return result

        if len(symbols) == 1:
            # Single ticker: data has simple columns (Close, Open, ...)
            sym = symbols[0]
            internal = reverse_map[sym]
            if 'Close' in data.columns:
                for idx, row in data.iterrows():
                    price = row['Close']
                    if price is not None and not (isinstance(price, float) and price != price):  # check NaN
                        month_key = idx.strftime('%Y-%m')
                        result[internal][month_key] = float(price)
        else:
            # Multiple tickers: data has MultiIndex columns (Close, sym1), (Close, sym2), ...
            close_data = data['Close'] if 'Close' in data.columns else None
            if close_data is not None:
                for sym in symbols:
                    if sym not in close_data.columns:
                        continue
                    internal = reverse_map[sym]
                    for idx, price in close_data[sym].items():
                        if price is not None and not (isinstance(price, float) and price != price):
                            month_key = idx.strftime('%Y-%m')
                            result[internal][month_key] = float(price)

    except Exception as e:
        logger.error(f"Error fetching historical prices: {e}")

    return result


def get_historical_exchange_rates(from_currency: str, to_currency: str, start_date: str) -> dict:
    """
    Fetch historical monthly exchange rates via yfinance.

    Args:
        from_currency: e.g. 'USD'
        to_currency: e.g. 'EUR'
        start_date: YYYY-MM-DD format

    Returns:
        {YYYY-MM: rate}
    """
    if from_currency == to_currency:
        return {}

    try:
        ticker_symbol = f"{from_currency}{to_currency}=X"
        data = yf.download(
            ticker_symbol,
            start=start_date,
            interval="1mo",
            auto_adjust=True,
            progress=False,
        )

        rates = {}
        if not data.empty and 'Close' in data.columns:
            for idx, row in data.iterrows():
                rate = row['Close']
                if rate is not None and not (isinstance(rate, float) and rate != rate):
                    month_key = idx.strftime('%Y-%m')
                    rates[month_key] = float(rate)

        return rates

    except Exception as e:
        logger.error(f"Error fetching historical exchange rates: {e}")
        return {}


def get_price_cache_status() -> dict:
    """Get overall price cache status: oldest/newest update times."""
    with get_db() as conn:
        row = conn.execute(
            'SELECT MIN(updated_at) as oldest, MAX(updated_at) as newest, COUNT(*) as cnt FROM price_cache'
        ).fetchone()
        return {
            'oldest_update': row[0] if row else None,
            'newest_update': row[1] if row else None,
            'cached_count': row[2] if row else 0,
        }


def refresh_all_prices(holdings_info: list) -> dict:
    """
    Force-refresh prices for all holdings.

    Args:
        holdings_info: List of dicts with 'ticker', 'price_ticker', 'isin', 'asset_type'

    Returns:
        Dict with refreshed count and errors
    """
    from .morningstar import get_fund_nav

    refreshed = 0
    errors = []

    for info in holdings_info:
        ticker = info['ticker']
        price_ticker = info['price_ticker']
        asset_type = info.get('asset_type', 'STOCK')
        isin = info.get('isin', '')

        try:
            if asset_type == 'FUND' and isin:
                # Clear cache first so get_fund_nav re-fetches
                with get_db() as conn:
                    conn.execute('DELETE FROM price_cache WHERE ticker = ?', (isin,))
                    conn.commit()
                result = get_fund_nav(isin)
            else:
                # Clear cache first so get_current_price re-fetches
                with get_db() as conn:
                    conn.execute('DELETE FROM price_cache WHERE ticker = ?', (price_ticker,))
                    conn.commit()
                result = get_current_price(price_ticker)

            if result:
                refreshed += 1
            else:
                errors.append(f"{ticker}: geen prijs gevonden")
        except Exception as e:
            errors.append(f"{ticker}: {str(e)}")

    # Also refresh exchange rate
    with get_db() as conn:
        conn.execute('DELETE FROM exchange_rate_cache')
        conn.commit()
    get_exchange_rate('USD', 'EUR')

    return {'refreshed': refreshed, 'errors': errors, 'total': len(holdings_info)}


def get_dividend_history(ticker: str, start_date: date) -> List[dict]:
    """
    Get dividend history for a ticker starting from a specific date.

    Args:
        ticker: Stock ticker symbol
        start_date: Start date for dividend history

    Returns:
        List of dividends with ex_date, amount, currency
    """
    try:
        stock = yf.Ticker(ticker)

        # Get dividend history
        dividends = stock.dividends

        if dividends.empty:
            return []

        # Filter dividends from start_date onwards
        dividends = dividends[dividends.index >= start_date.strftime('%Y-%m-%d')]

        # Get currency info
        info = stock.info
        currency = info.get('currency', 'USD')

        # Convert to list of dicts
        result = []
        for div_date, amount in dividends.items():
            result.append({
                'ex_date': div_date.strftime('%Y-%m-%d'),
                'amount': float(amount),
                'currency': currency
            })

        return result

    except Exception as e:
        logger.error(f"Error fetching dividend history for {ticker}: {e}")
        return []


def get_dividend_info(ticker: str) -> Optional[dict]:
    """
    Fetch dividend metadata from yfinance for forecast calculations.

    Returns dict with dividend_rate, trailing_annual_rate, ex_dividend_date,
    last_dividend_value, currency, and historical_dividends (last 3 years).
    Cached in-memory for 24 hours.
    """
    import time

    # Check in-memory cache
    cached = _dividend_info_cache.get(ticker)
    if cached and (time.time() - cached['timestamp']) < DIVIDEND_INFO_CACHE_TTL:
        return cached['data']

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Get historical dividends (last 3 years)
        dividends = stock.dividends
        historical = []
        if not dividends.empty:
            three_years_ago = (datetime.now() - __import__('datetime').timedelta(days=3 * 365)).strftime('%Y-%m-%d')
            recent_divs = dividends[dividends.index >= three_years_ago]
            for div_date, amount in recent_divs.items():
                historical.append({
                    'date': div_date.strftime('%Y-%m-%d'),
                    'amount': float(amount),
                })

        # Parse ex_dividend_date (can be Unix timestamp)
        raw_ex_date = info.get('exDividendDate')
        ex_date_str = None
        if raw_ex_date:
            if isinstance(raw_ex_date, (int, float)):
                try:
                    ex_date_str = date.fromtimestamp(raw_ex_date).isoformat()
                except (ValueError, OSError):
                    pass
            elif isinstance(raw_ex_date, str):
                ex_date_str = raw_ex_date

        result = {
            'dividend_rate': info.get('dividendRate'),
            'trailing_annual_rate': info.get('trailingAnnualDividendRate'),
            'ex_dividend_date': ex_date_str,
            'last_dividend_value': info.get('lastDividendValue'),
            'currency': info.get('currency', 'USD'),
            'historical_dividends': historical,
        }

        _dividend_info_cache[ticker] = {'data': result, 'timestamp': time.time()}
        return result

    except Exception as e:
        logger.error(f"Error fetching dividend info for {ticker}: {e}")
        return None


VALID_MOVER_PERIODS = {'5d', '1mo', 'ytd', '1y'}


def get_period_changes(yahoo_tickers: dict, period: str) -> dict:
    """
    Fetch price changes over a period for multiple tickers via a single yf.download().

    Args:
        yahoo_tickers: {internal_ticker: yahoo_ticker_symbol}
        period: yfinance period string ('5d', '1mo', 'ytd', '1y')

    Returns:
        {internal_ticker: change_percent} where change_percent = ((last - first) / first) * 100
    """
    if not yahoo_tickers or period not in VALID_MOVER_PERIODS:
        return {}

    # Check in-memory cache
    cache_key = f"{period}:{','.join(sorted(yahoo_tickers.values()))}"
    cached = _period_changes_cache.get(cache_key)
    if cached and (_time.time() - cached['timestamp']) < PERIOD_CHANGES_CACHE_TTL:
        return cached['data']

    reverse_map = {}
    symbols = []
    for internal, yahoo_sym in yahoo_tickers.items():
        reverse_map[yahoo_sym] = internal
        symbols.append(yahoo_sym)

    result = {}
    try:
        data = yf.download(
            symbols,
            period=period,
            auto_adjust=True,
            progress=False,
        )

        if data.empty:
            return result

        if len(symbols) == 1:
            sym = symbols[0]
            internal = reverse_map[sym]
            if 'Close' in data.columns and len(data) >= 2:
                first_close = float(data['Close'].iloc[0])
                last_close = float(data['Close'].iloc[-1])
                if first_close and first_close != 0:
                    result[internal] = ((last_close - first_close) / first_close) * 100
        else:
            close_data = data['Close'] if 'Close' in data.columns else None
            if close_data is not None:
                for sym in symbols:
                    if sym not in close_data.columns:
                        continue
                    col = close_data[sym].dropna()
                    if len(col) < 2:
                        continue
                    internal = reverse_map[sym]
                    first_close = float(col.iloc[0])
                    last_close = float(col.iloc[-1])
                    if first_close and first_close != 0:
                        result[internal] = ((last_close - first_close) / first_close) * 100

    except Exception as e:
        logger.error(f"Error fetching period changes ({period}): {e}")

    _period_changes_cache[cache_key] = {'data': result, 'timestamp': _time.time()}
    return result
