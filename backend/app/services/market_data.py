"""
Market data service for fetching prices and exchange rates from Yahoo Finance and Finnhub.
"""
import yfinance as yf
import finnhub
from typing import Optional, List
from datetime import datetime, date
from .database import get_db, get_cached_exchange_rate, save_exchange_rate_to_cache, get_user_settings


def get_current_price(ticker: str) -> Optional[dict]:
    """
    Fetch current price from Yahoo Finance, with Finnhub as fallback.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with current_price, change_percent, currency or None if unavailable
    """
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

        return {
            'current_price': current_price,
            'change_percent': change_percent,
            'currency': currency
        }
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
    Lookup stock information by ISIN using Finnhub (preferred for European ISINs) and Yahoo Finance.

    Args:
        isin: International Securities Identification Number

    Returns:
        Dict with ticker, name, currency, country, etc. or None if not found
    """
    # Check if ISIN is European (starts with country codes from Europe)
    european_prefixes = ['AT', 'BE', 'CY', 'DE', 'ES', 'FI', 'FR', 'GB', 'GR', 'IE', 'IT', 'LU', 'NL', 'PT']
    is_european = any(isin.startswith(prefix) for prefix in european_prefixes)

    # Try Finnhub first for European ISINs
    if is_european:
        result = lookup_by_isin_finnhub(isin)
        if result:
            return result

    # Try Yahoo Finance with ISIN directly
    try:
        stock = yf.Ticker(isin)
        info = stock.info

        if info and info.get('symbol'):
            # Got a result from ISIN lookup
            ticker = info.get('symbol', '')
            base_ticker = ticker.split('.')[0]  # Remove exchange suffix if present

            # Check if this ticker actually has price data
            hist = stock.history(period='1d')
            ticker_has_data = not hist.empty

            # If European ISIN or ticker has no data, try to find EUR-denominated version on exchanges
            if is_european or not ticker_has_data:
                # Try to find EUR-denominated version on European exchanges
                euro_exchanges = ['.DE', '.PA', '.AS', '.MI', '.BR']
                found_eur_version = False

                for exchange in euro_exchanges:
                    try:
                        test_ticker = base_ticker + exchange
                        test_stock = yf.Ticker(test_ticker)
                        test_hist = test_stock.history(period='1d')
                        if not test_hist.empty:
                            test_info = test_stock.info
                            if test_info.get('currency') == 'EUR':
                                # Found EUR version with data, use this instead
                                info = test_info
                                ticker = test_ticker
                                hist = test_hist
                                found_eur_version = True
                                ticker_has_data = True
                                break
                    except:
                        continue

                # If original ticker has no data and we didn't find EUR version, fail
                if not ticker_has_data and not found_eur_version:
                    print(f"Warning: European ISIN {isin} found as {ticker} but no price data available")
                    # Return None so we try Finnhub as fallback
                    return None

                # If no EUR version found, keep the original ticker but warn about currency
                if not found_eur_version and info.get('currency') != 'EUR':
                    print(f"Warning: European ISIN {isin} found as {ticker} in {info.get('currency')}, not EUR")
        else:
            # ISIN lookup failed, try Finnhub
            if not is_european:
                result = lookup_by_isin_finnhub(isin)
                if result:
                    return result
            return None

        name = info.get('longName') or info.get('shortName', '')
        currency = info.get('currency', 'USD')
        country = info.get('country', 'Verenigde Staten')

        # Map country names to Dutch
        country_map = {
            'United States': 'Verenigde Staten',
            'Netherlands': 'Nederland',
            'Germany': 'Duitsland',
            'France': 'Frankrijk',
            'United Kingdom': 'Verenigd Koninkrijk',
            'Belgium': 'België',
        }
        country = country_map.get(country, country)

        # Determine asset type
        sector = info.get('sector', '')
        asset_type = 'REIT' if 'REIT' in sector or 'Real Estate' in sector else 'STOCK'

        # Get current price (reuse hist if we already fetched it, otherwise get more history)
        if not hist.empty:
            current_price = float(hist['Close'].iloc[-1])
        else:
            price_stock = yf.Ticker(ticker)
            hist = price_stock.history(period='5d')
            current_price = float(hist['Close'].iloc[-1]) if not hist.empty else None

        # Check if stock pays dividends
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
            'dividend_yield': dividend_yield
        }

    except Exception as e:
        print(f"Error looking up ISIN {isin}: {e}")
        return None


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
        print(f"Error looking up ISIN {isin} via Finnhub: {e}")
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

        return {
            'current_price': current_price,
            'change_percent': change_percent,
            'currency': currency
        }

    except Exception as e:
        print(f"Error fetching price for {ticker} via Finnhub: {e}")
        return None


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
        print(f"Error fetching dividend history for {ticker}: {e}")
        return []
