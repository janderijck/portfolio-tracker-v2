import logging
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from ..models import StockInfo, StockInfoCreate, ManualPrice, ManualPriceCreate
from ..services.database import (
    get_db, get_all_stocks, get_stock_info, insert_stock_info, update_stock_info, delete_stock_info,
    search_stocks, get_stocks_missing_yahoo_ticker, update_stock_yahoo_ticker,
    get_all_transactions, get_latest_manual_price, get_manual_prices, insert_manual_price, update_manual_price, delete_manual_price,
    get_all_dividends,
)
from ..services.market_data import (
    get_current_price, lookup_by_isin, get_fund_price, get_cached_price_only,
    openfigi_map_isin, openfigi_search, resolve_yahoo_ticker_from_isin, get_dividend_info,
)
from ..services.dividend_forecast import detect_dividend_frequency, estimate_next_dividend_amount, project_future_ex_dates

router = APIRouter(prefix="/api", tags=["stocks"])


@router.get("/stocks", response_model=List[StockInfo])
async def get_stocks():
    """Get all stocks."""
    with get_db() as conn:
        stocks = get_all_stocks(conn)
        return [StockInfo(**stock) for stock in stocks]


@router.get("/watchlist")
async def get_watchlist():
    """Get stocks without positions (watchlist) with current prices."""
    with get_db() as conn:
        # Get all stocks
        all_stocks = get_all_stocks(conn)

        # Get tickers that have positions
        all_transactions = get_all_transactions(conn)
        tickers_with_positions = set()

        # Calculate which tickers have positive positions
        holdings = {}
        for tx in all_transactions:
            ticker = tx['ticker']
            if ticker not in holdings:
                holdings[ticker] = 0
            if tx['transaction_type'] == 'BUY':
                holdings[ticker] += tx['quantity']
            else:
                holdings[ticker] -= tx['quantity']

        for ticker, qty in holdings.items():
            if qty > 0:
                tickers_with_positions.add(ticker)

        # Filter to stocks without positions
        watchlist = []
        for stock in all_stocks:
            if stock['ticker'] not in tickers_with_positions:
                # Determine the ticker to use for price fetching
                price_ticker = stock.get('yahoo_ticker') or stock['ticker']

                # Fetch current price
                if stock.get('manual_price_tracking'):
                    manual_price = get_latest_manual_price(conn, stock['ticker'])
                    if manual_price:
                        current_price = manual_price['price']
                        currency = manual_price['currency']
                    else:
                        # Fallback to automatic price if no manual price available
                        price_info = get_current_price(price_ticker)
                        current_price = price_info['current_price'] if price_info else None
                        currency = price_info['currency'] if price_info else 'EUR'
                else:
                    price_info = get_current_price(price_ticker)
                    current_price = price_info['current_price'] if price_info else None
                    currency = price_info['currency'] if price_info else 'EUR'

                watchlist.append({
                    **stock,
                    'current_price': current_price,
                    'currency': currency
                })

        return watchlist


@router.get("/stocks/search")
async def search_stocks_endpoint(q: str = Query(..., min_length=1)):
    """Search stocks by ticker, name, or ISIN - local DB + OpenFIGI."""
    with get_db() as conn:
        # 1. Search local database
        local_results = search_stocks(conn, q)

        # 1b. Lazy enrich local results missing yahoo_ticker
        for result in local_results:
            if not result.get('yahoo_ticker') and result.get('isin') and not result.get('manual_price_tracking'):
                try:
                    yahoo_ticker = resolve_yahoo_ticker_from_isin(result['isin'])
                    if yahoo_ticker:
                        update_stock_yahoo_ticker(conn, result['ticker'], yahoo_ticker)
                        result['yahoo_ticker'] = yahoo_ticker
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Non-critical error resolving Yahoo ticker for {result['ticker']}: {e}")

        # 2. Search via OpenFIGI for external results
        external_results = []
        if len(q) >= 2:
            try:
                query_upper = q.upper()
                is_isin = len(query_upper) == 12 and query_upper[:2].isalpha()

                if is_isin:
                    figi_results = openfigi_map_isin(query_upper)
                else:
                    figi_results = openfigi_search(q)

                for r in figi_results:
                    external_results.append({
                        'ticker': r['yahoo_ticker'],
                        'isin': query_upper if is_isin else '',
                        'name': r['name'],
                        'asset_type': 'STOCK',
                        'country': r.get('country', 'Onbekend'),
                        'yahoo_ticker': r['yahoo_ticker'],
                        'manual_price_tracking': 0,
                        'current_price': None,
                        'currency': r.get('currency', 'USD'),
                        'pays_dividend': False,
                        'dividend_yield': None,
                        'from_openfigi': True,
                    })
            except Exception as e:
                logging.getLogger(__name__).warning(f"Non-critical error searching OpenFIGI for '{q}': {e}")

        # 3. Morningstar for ISIN fund searches (always try for ISINs)
        if len(q) >= 2:
            query_upper = q.upper()
            is_isin = len(query_upper) == 12 and query_upper[:2].isalpha()
            if is_isin:
                try:
                    from ..services.morningstar import search_fund_by_isin
                    ms_result = search_fund_by_isin(query_upper)
                    if ms_result:
                        # Add Morningstar result (will be deduplicated if already in local)
                        external_results.append({
                            'ticker': query_upper,
                            'isin': query_upper,
                            'name': ms_result['name'],
                            'asset_type': 'FUND',
                            'country': 'België',
                            'yahoo_ticker': None,
                            'manual_price_tracking': 0,
                            'current_price': ms_result.get('current_price'),
                            'currency': ms_result.get('currency', 'EUR'),
                            'pays_dividend': True,
                            'dividend_yield': None,
                            'from_morningstar': True,
                        })
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Non-critical error searching Morningstar for ISIN '{query_upper}': {e}")

        # 4. Combine: local first, then external (deduplicate on ticker)
        local_tickers = {r['ticker'] for r in local_results}
        combined = local_results + [e for e in external_results if e['ticker'] not in local_tickers]

        return combined


@router.post("/stocks/enrich")
async def enrich_stocks():
    """
    Enrich all stocks that have an ISIN but no yahoo_ticker.
    Uses OpenFIGI ISIN lookup with rate limiting (250ms between calls).
    """
    import asyncio

    with get_db() as conn:
        missing = get_stocks_missing_yahoo_ticker(conn)

        if not missing:
            return {"message": "Alle stocks hebben al een yahoo_ticker", "enriched": 0, "total": 0}

        enriched = 0
        results = []

        for stock in missing:
            isin = stock['isin']
            ticker = stock['ticker']

            yahoo_ticker = resolve_yahoo_ticker_from_isin(isin)
            if yahoo_ticker:
                update_stock_yahoo_ticker(conn, ticker, yahoo_ticker)
                enriched += 1
                results.append({"ticker": ticker, "isin": isin, "yahoo_ticker": yahoo_ticker})
            else:
                results.append({"ticker": ticker, "isin": isin, "yahoo_ticker": None, "error": "Niet gevonden"})

            # Rate limit: 250ms between OpenFIGI calls
            await asyncio.sleep(0.25)

        return {
            "message": f"{enriched} van {len(missing)} stocks verrijkt",
            "enriched": enriched,
            "total": len(missing),
            "results": results,
        }


@router.post("/stocks", response_model=StockInfo)
async def create_stock(stock: StockInfoCreate):
    """Add a new stock."""
    with get_db() as conn:
        existing = get_stock_info(conn, stock.ticker)
        if existing:
            raise HTTPException(status_code=400, detail=f"Stock {stock.ticker} already exists")

        stock_id = insert_stock_info(conn, stock.model_dump())
        return StockInfo(id=stock_id, **stock.model_dump())


@router.get("/stocks/lookup/{isin}")
async def lookup_stock(isin: str):
    """Lookup stock information by ISIN via Yahoo Finance."""
    result = lookup_by_isin(isin)
    if result:
        return result
    raise HTTPException(status_code=404, detail=f"Could not find stock with ISIN {isin}")


@router.put("/stocks/{ticker}", response_model=StockInfo)
async def update_stock(ticker: str, stock: StockInfoCreate):
    """Update a stock."""
    with get_db() as conn:
        if not update_stock_info(conn, ticker, stock.model_dump()):
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        updated = get_stock_info(conn, ticker)
        return StockInfo(**updated)


@router.delete("/stocks/{ticker}")
async def remove_stock(ticker: str):
    """Delete a stock."""
    with get_db() as conn:
        if delete_stock_info(conn, ticker):
            return {"message": f"Stock {ticker} deleted"}
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")


@router.get("/stocks/{ticker}")
async def get_stock_detail(ticker: str):
    """Get detailed information about a stock."""
    from datetime import date as date_type

    with get_db() as conn:
        info = get_stock_info(conn, ticker)
        transactions = get_all_transactions(conn, ticker)
        dividends = get_all_dividends(conn, ticker)

        price_info = None
        if info and info.get('asset_type') == 'FUND':
            isin = info.get('isin')
            if isin:
                price_info = get_fund_price(ticker, isin)
        if price_info is None:
            price_ticker = (info.get('yahoo_ticker') or ticker) if info else ticker
            price_info = get_current_price(price_ticker)

        # Build upcoming ex-dividend forecast
        upcoming_dividends = []
        if info and info.get('pays_dividend'):
            try:
                yahoo_ticker = info.get('yahoo_ticker') or ticker
                div_info = get_dividend_info(yahoo_ticker)
                if div_info:
                    hist_divs = div_info.get('historical_dividends', [])
                    hist_dates = []
                    hist_amounts = []
                    for hd in hist_divs:
                        try:
                            hist_dates.append(date_type.fromisoformat(hd['date']))
                            hist_amounts.append(hd['amount'])
                        except (ValueError, KeyError):
                            continue

                    if hist_dates:
                        frequency = detect_dividend_frequency(hist_dates)
                        per_share = estimate_next_dividend_amount(
                            hist_amounts,
                            div_info.get('dividend_rate'),
                            frequency,
                        )
                        if per_share > 0:
                            last_ex = max(hist_dates)
                            future_dates = project_future_ex_dates(last_ex, frequency, 12)
                            currency = div_info.get('currency', 'USD')
                            for fd in future_dates:
                                upcoming_dividends.append({
                                    "ex_date": fd.isoformat(),
                                    "estimated_per_share": round(per_share, 4),
                                    "currency": currency,
                                    "frequency": frequency,
                                })
            except Exception as e:
                logging.getLogger(__name__).warning(f"Non-critical error fetching dividend forecast for {ticker}: {e}")

        return {
            "info": info,
            "transactions": transactions,
            "dividends": dividends,
            "current_price": price_info,
            "upcoming_dividends": upcoming_dividends,
        }


@router.get("/stocks/{ticker}/history")
async def get_stock_history(ticker: str, period: str = Query(default="1y", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$")):
    """
    Get historical price data for a stock.

    Args:
        ticker: Stock ticker symbol
        period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

    Returns:
        List of {date, price} objects
    """
    import yfinance as yf

    with get_db() as conn:
        stock_info = get_stock_info(conn, ticker)
        if not stock_info:
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        # Check if manual price tracking is enabled
        if stock_info.get('manual_price_tracking'):
            # Return manual prices from database
            manual_prices = get_manual_prices(conn, ticker)
            if manual_prices:
                return [
                    {
                        "date": price['date'],
                        "price": float(price['price'])
                    }
                    for price in sorted(manual_prices, key=lambda x: x['date'])
                ]
            else:
                return []

        # FUND type: use Morningstar for history
        if stock_info.get('asset_type') == 'FUND':
            isin = stock_info.get('isin')
            if isin:
                from ..services.morningstar import get_fund_nav_history
                history = get_fund_nav_history(isin, period)
                if history:
                    return history
            # Fallback to manual prices for FUND
            manual_prices = get_manual_prices(conn, ticker)
            if manual_prices:
                return [
                    {
                        "date": price['date'],
                        "price": float(price['price'])
                    }
                    for price in sorted(manual_prices, key=lambda x: x['date'])
                ]
            return []

        # Get historical data from Yahoo Finance
        try:
            yahoo_ticker = stock_info.get('yahoo_ticker') or ticker
            stock = yf.Ticker(yahoo_ticker)
            hist = stock.history(period=period)

            if hist.empty:
                raise HTTPException(status_code=404, detail=f"No historical data found for {ticker}")

            # Convert to simple list of {date, price}
            data = [
                {
                    "date": date.strftime('%Y-%m-%d'),
                    "price": float(row['Close'])
                }
                for date, row in hist.iterrows()
            ]

            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching historical data: {str(e)}")


# =============================================================================
# Manual Price Endpoints
# =============================================================================

@router.get("/stocks/{ticker}/prices", response_model=List[ManualPrice])
async def get_stock_prices(ticker: str):
    """Get all manual prices for a stock."""
    with get_db() as conn:
        prices = get_manual_prices(conn, ticker)
        return [ManualPrice(**p) for p in prices]


@router.post("/stocks/{ticker}/prices", response_model=ManualPrice)
async def add_stock_price(ticker: str, price: ManualPriceCreate):
    """Add a manual price for a stock."""
    with get_db() as conn:
        price_data = price.model_dump()
        price_data['ticker'] = ticker
        price_id = insert_manual_price(conn, price_data)
        return ManualPrice(id=price_id, **price_data)


@router.put("/stocks/{ticker}/prices/{price_id}", response_model=ManualPrice)
async def edit_stock_price(ticker: str, price_id: int, price: ManualPriceCreate):
    """Update a manual price."""
    with get_db() as conn:
        price_data = price.model_dump()
        if not update_manual_price(conn, price_id, price_data):
            raise HTTPException(status_code=404, detail="Price not found")
        return ManualPrice(id=price_id, **price_data)


@router.delete("/stocks/{ticker}/prices/{price_id}")
async def remove_stock_price(ticker: str, price_id: int):
    """Delete a manual price."""
    with get_db() as conn:
        if delete_manual_price(conn, price_id):
            return {"message": "Price deleted"}
        raise HTTPException(status_code=404, detail="Price not found")
