"""
Portfolio Tracker API - Main application.

Routes only - business logic is in services.
"""
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from .models import (
    Transaction, TransactionCreate, Dividend, DividendCreate,
    PortfolioHolding, PortfolioSummary, PortfolioResponse,
    StockInfo, StockInfoCreate,
    PerformanceSummary, DividendSummary, CostSummary, AllocationSummary, AllocationItem,
    UserSettings, ManualPrice, ManualPriceCreate
)
from .services.database import (
    get_db,
    insert_transaction, get_all_transactions, update_transaction, delete_transaction,
    insert_dividend, get_all_dividends, update_dividend, delete_dividend,
    get_stock_info, get_all_stocks, insert_stock_info, update_stock_info, delete_stock_info,
    get_available_brokers, search_stocks,
    get_user_settings, update_user_settings,
    insert_manual_price, get_manual_prices, get_latest_manual_price, delete_manual_price, update_manual_price,
)
from .services.market_data import get_current_price, get_exchange_rate, lookup_by_isin, get_dividend_history
from .services.calculations import calculate_holding_metrics

app = FastAPI(
    title="Portfolio Tracker API",
    description="API for tracking stock portfolio and dividends",
    version="2.0.0"
)

# CORS middleware
# Get frontend URL from environment variable (for Azure deployment)
frontend_url = os.getenv("FRONTEND_URL", "")
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080",
]

# Add Azure Container Apps frontend URL if configured
if frontend_url:
    allowed_origins.append(frontend_url)

# Also allow any azurecontainerapps.io subdomain
allowed_origin_patterns = [
    r"https://.*\.azurecontainerapps\.io",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.azurecontainerapps\.io",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Portfolio Tracker API v2", "status": "running"}


# =============================================================================
# Portfolio Endpoints
# =============================================================================

@app.get("/api/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    """
    Get all portfolio holdings with calculated metrics.

    Calculations are done at request time using pure functions.
    """
    with get_db() as conn:
        # Get all transactions grouped by ticker
        all_transactions = get_all_transactions(conn)

        if not all_transactions:
            return PortfolioResponse(
                holdings=[],
                summary=PortfolioSummary(
                    total_invested_eur=0,
                    total_current_value_eur=0,
                    total_gain_loss_eur=0,
                    total_gain_loss_percent=0
                )
            )

        # Group transactions by ticker
        by_ticker = {}
        for tx in all_transactions:
            ticker = tx['ticker']
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(tx)

        # Get current exchange rate
        usd_eur_rate = get_exchange_rate('USD', 'EUR')

        holdings = []
        total_invested_eur = 0
        total_current_value_eur = 0

        for ticker, transactions in by_ticker.items():
            # Check if stock uses manual price tracking
            stock_info_data = get_stock_info(conn, ticker)
            uses_manual = stock_info_data and stock_info_data.get('manual_price_tracking')
            pays_dividend = stock_info_data.get('pays_dividend', False) if stock_info_data else False
            manual_price_date = None

            if uses_manual:
                # Get latest manual price
                manual_price = get_latest_manual_price(conn, ticker)
                if manual_price:
                    current_price = manual_price['price']
                    currency = manual_price['currency']
                    manual_price_date = manual_price['date']
                else:
                    # Fallback to automatic price if no manual price available
                    price_info = get_current_price(ticker)
                    current_price = price_info['current_price'] if price_info else None
                    currency = price_info['currency'] if price_info else transactions[0]['currency']
            else:
                # Get current price from Yahoo Finance/Finnhub
                price_info = get_current_price(ticker)
                current_price = price_info['current_price'] if price_info else None
                currency = price_info['currency'] if price_info else 'USD'

            # Calculate metrics using pure functions
            exchange_rate = usd_eur_rate if currency == 'USD' else 1.0
            metrics = calculate_holding_metrics(transactions, current_price, exchange_rate)

            # Skip if no quantity held
            if metrics['quantity'] <= 0:
                continue

            # Get metadata from first transaction
            first_tx = transactions[0]

            holding = PortfolioHolding(
                ticker=ticker,
                isin=first_tx['isin'],
                name=first_tx['name'],
                broker=first_tx['broker'],
                quantity=metrics['quantity'],
                avg_purchase_price=metrics['avg_purchase_price'],
                total_invested=metrics['total_invested'],
                total_invested_eur=metrics['total_invested_eur'],
                total_fees=metrics['total_fees'],
                currency=first_tx['currency'],
                current_price=metrics['current_price'],
                current_value=metrics['current_value'],
                gain_loss=metrics['gain_loss'],
                gain_loss_percent=metrics['gain_loss_percent'],
                is_usd_account=metrics['is_usd_account'],
                manual_price_date=manual_price_date,
                pays_dividend=pays_dividend
            )
            holdings.append(holding)

            # Aggregate totals (convert USD to EUR)
            total_invested_eur += metrics['total_invested_eur']
            if metrics['current_value']:
                if metrics['is_usd_account']:
                    # Convert USD current value to EUR
                    total_current_value_eur += metrics['current_value'] * exchange_rate
                else:
                    # EUR current value
                    total_current_value_eur += metrics['current_value']

        # Calculate summary
        total_gain_loss_eur = total_current_value_eur - total_invested_eur
        total_gain_loss_percent = (total_gain_loss_eur / total_invested_eur * 100) if total_invested_eur > 0 else 0

        summary = PortfolioSummary(
            total_invested_eur=round(total_invested_eur, 2),
            total_current_value_eur=round(total_current_value_eur, 2),
            total_gain_loss_eur=round(total_gain_loss_eur, 2),
            total_gain_loss_percent=round(total_gain_loss_percent, 2)
        )

        return PortfolioResponse(holdings=holdings, summary=summary)


# =============================================================================
# Transaction Endpoints
# =============================================================================

@app.get("/api/transactions", response_model=List[Transaction])
async def get_transactions(ticker: Optional[str] = None):
    """Get all transactions, optionally filtered by ticker."""
    with get_db() as conn:
        transactions = get_all_transactions(conn, ticker)
        return [Transaction(**tx) for tx in transactions]


@app.post("/api/transactions", response_model=Transaction)
async def create_transaction(transaction: TransactionCreate):
    """Create a new transaction."""
    with get_db() as conn:
        tx_id = insert_transaction(conn, transaction.model_dump())
        return Transaction(id=tx_id, **transaction.model_dump())


@app.put("/api/transactions/{transaction_id}", response_model=Transaction)
async def edit_transaction(transaction_id: int, transaction: TransactionCreate):
    """Update a transaction."""
    with get_db() as conn:
        if not update_transaction(conn, transaction_id, transaction.model_dump()):
            raise HTTPException(status_code=404, detail="Transaction not found")
        return Transaction(id=transaction_id, **transaction.model_dump())


@app.delete("/api/transactions/{transaction_id}")
async def remove_transaction(transaction_id: int):
    """Delete a transaction."""
    with get_db() as conn:
        if delete_transaction(conn, transaction_id):
            return {"message": "Transaction deleted"}
        raise HTTPException(status_code=404, detail="Transaction not found")


# =============================================================================
# Dividend Endpoints
# =============================================================================

@app.get("/api/dividends", response_model=List[Dividend])
async def get_dividends(ticker: Optional[str] = None):
    """Get all dividends, optionally filtered by ticker."""
    with get_db() as conn:
        dividends = get_all_dividends(conn, ticker)
        return [Dividend(**div) for div in dividends]


@app.post("/api/dividends", response_model=Dividend)
async def create_dividend(dividend: DividendCreate):
    """Create a new dividend."""
    with get_db() as conn:
        div_id = insert_dividend(conn, dividend.model_dump())
        return Dividend(id=div_id, **dividend.model_dump())


@app.put("/api/dividends/{dividend_id}", response_model=Dividend)
async def edit_dividend(dividend_id: int, dividend: DividendCreate):
    """Update a dividend."""
    with get_db() as conn:
        if not update_dividend(conn, dividend_id, dividend.model_dump()):
            raise HTTPException(status_code=404, detail="Dividend not found")
        return Dividend(id=dividend_id, **dividend.model_dump())


@app.delete("/api/dividends/{dividend_id}")
async def remove_dividend(dividend_id: int):
    """Delete a dividend."""
    with get_db() as conn:
        if delete_dividend(conn, dividend_id):
            return {"message": "Dividend deleted"}
        raise HTTPException(status_code=404, detail="Dividend not found")


@app.post("/api/dividends/fetch-history/{ticker}")
async def fetch_dividend_history(ticker: str):
    """
    Fetch dividend history from Yahoo Finance and add to database.
    Only fetches dividends from the first purchase date onwards.
    Automatically calculates total dividend based on shares held and applies withholding tax.
    """
    with get_db() as conn:
        # Get all transactions for this ticker to find earliest date
        transactions = get_all_transactions(conn, ticker)
        if not transactions:
            raise HTTPException(status_code=404, detail="No transactions found for ticker")

        # Get earliest transaction date (convert string to date if needed)
        earliest_date_str = min(tx['date'] for tx in transactions)
        if isinstance(earliest_date_str, str):
            from datetime import datetime
            earliest_date = datetime.strptime(earliest_date_str, '%Y-%m-%d').date()
        else:
            earliest_date = earliest_date_str

        # Get stock info for ISIN and country
        stock_info = get_stock_info(conn, ticker)
        if not stock_info:
            raise HTTPException(status_code=404, detail="Stock not found")

        isin = stock_info['isin']
        country = stock_info.get('country', '')

        # Determine withholding tax rate based on country
        # For Belgian investors (assuming DEGIRO Belgium)
        withholding_rates = {
            'Verenigde Staten': 0.15,  # 15% US withholding
            'Nederland': 0.15,  # 15% NL withholding
            'België': 0.30,  # 30% BE withholding
            'Duitsland': 0.2638,  # ~26.38% DE withholding
            'Frankrijk': 0.30,  # 30% FR withholding (can be reduced with treaty)
        }
        withholding_rate = withholding_rates.get(country, 0.30)  # Default 30%

        # Fetch dividend history
        dividend_history = get_dividend_history(ticker, earliest_date)

        if not dividend_history:
            return {"message": "No dividends found", "count": 0}

        # Get existing dividends to avoid duplicates
        existing_dividends = get_all_dividends(conn, ticker)
        existing_dates = {div['ex_date'] for div in existing_dividends}

        # Insert new dividends
        added_count = 0
        for div in dividend_history:
            ex_date_str = div['ex_date']
            if ex_date_str not in existing_dates:
                # Calculate number of shares held on ex-date
                shares_on_ex_date = 0
                for tx in transactions:
                    tx_date_str = tx['date'] if isinstance(tx['date'], str) else tx['date'].strftime('%Y-%m-%d')
                    if tx_date_str <= ex_date_str:
                        if tx['transaction_type'] == 'BUY':
                            shares_on_ex_date += tx['quantity']
                        else:  # SELL
                            shares_on_ex_date -= tx['quantity']

                # Calculate total dividend
                dividend_per_share = div['amount']
                total_bruto = dividend_per_share * shares_on_ex_date
                withheld_amount = total_bruto * withholding_rate
                net_received = total_bruto - withheld_amount

                dividend_data = {
                    'ticker': ticker,
                    'isin': isin,
                    'ex_date': ex_date_str,
                    'bruto_amount': round(total_bruto, 2),
                    'currency': div['currency'],
                    'withheld_tax': round(withheld_amount, 2),
                    'net_amount': round(net_received, 2),
                    'received': True,
                    'notes': f'Auto-imported: €{dividend_per_share:.4f}/aandeel × {shares_on_ex_date} aandelen ({country}: {withholding_rate*100:.0f}% inhouding)'
                }
                insert_dividend(conn, dividend_data)
                added_count += 1

        return {
            "message": f"Added {added_count} dividends",
            "count": added_count,
            "total_found": len(dividend_history)
        }


# =============================================================================
# Stock Info Endpoints
# =============================================================================

@app.get("/api/stocks", response_model=List[StockInfo])
async def get_stocks():
    """Get all stocks."""
    with get_db() as conn:
        stocks = get_all_stocks(conn)
        return [StockInfo(**stock) for stock in stocks]


@app.get("/api/watchlist")
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
                # Fetch current price
                if stock.get('manual_price_tracking'):
                    manual_price = get_latest_manual_price(conn, stock['ticker'])
                    if manual_price:
                        current_price = manual_price['price']
                        currency = manual_price['currency']
                    else:
                        # Fallback to automatic price if no manual price available
                        price_info = get_current_price(stock['ticker'])
                        current_price = price_info['current_price'] if price_info else None
                        currency = price_info['currency'] if price_info else 'EUR'
                else:
                    price_info = get_current_price(stock['ticker'])
                    current_price = price_info['current_price'] if price_info else None
                    currency = price_info['currency'] if price_info else 'EUR'

                watchlist.append({
                    **stock,
                    'current_price': current_price,
                    'currency': currency
                })

        return watchlist


@app.get("/api/stocks/search")
async def search_stocks_endpoint(q: str = Query(..., min_length=1)):
    """Search stocks by ticker, name, or ISIN - both local and Yahoo Finance."""
    with get_db() as conn:
        # First search local database
        local_results = search_stocks(conn, q)

        # Then try Yahoo Finance lookup
        yahoo_results = []
        if len(q) >= 2:
            try:
                query_upper = q.upper()

                # Check if it looks like an ISIN (12 chars, starts with 2 letters)
                is_isin = len(query_upper) == 12 and query_upper[:2].isalpha()

                if is_isin:
                    # Try ISIN directly
                    ticker_variants = [query_upper]
                else:
                    # Try as ticker symbol with exchange suffixes
                    ticker_variants = [query_upper]
                    if '.' not in query_upper:
                        ticker_variants.extend([
                            f"{query_upper}.BR",  # Brussels
                            f"{query_upper}.AS",  # Amsterdam
                            f"{query_upper}.PA",  # Paris
                            f"{query_upper}.DE",  # Germany
                            f"{query_upper}.L",   # London
                            f"{query_upper}.AX",  # Australia
                            f"{query_upper}.TO",  # Toronto
                            f"{query_upper}.MI",  # Milan
                            f"{query_upper}.SW",  # Swiss
                        ])

                for variant in ticker_variants:
                    yahoo_result = lookup_by_isin(variant)
                    if yahoo_result and yahoo_result.get('name'):
                        yahoo_results.append({
                            'ticker': yahoo_result['ticker'],
                            'isin': query_upper if is_isin else yahoo_result.get('isin', ''),
                            'name': yahoo_result['name'],
                            'asset_type': yahoo_result.get('asset_type', 'STOCK'),
                            'country': yahoo_result.get('country', 'Onbekend'),
                            'yahoo_ticker': yahoo_result.get('yahoo_ticker'),
                            'manual_price_tracking': 0,
                            'current_price': yahoo_result.get('current_price'),
                            'currency': yahoo_result.get('currency', 'USD'),
                            'pays_dividend': yahoo_result.get('pays_dividend', False),
                            'dividend_yield': yahoo_result.get('dividend_yield'),
                            'from_yahoo': True
                        })
                        break  # Found one, stop trying variants
            except:
                pass

        # Combine results, local first, then Yahoo (avoiding duplicates)
        local_tickers = {r['ticker'] for r in local_results}
        combined = local_results + [y for y in yahoo_results if y['ticker'] not in local_tickers]

        return combined


@app.post("/api/stocks", response_model=StockInfo)
async def create_stock(stock: StockInfoCreate):
    """Add a new stock."""
    with get_db() as conn:
        existing = get_stock_info(conn, stock.ticker)
        if existing:
            raise HTTPException(status_code=400, detail=f"Stock {stock.ticker} already exists")

        stock_id = insert_stock_info(conn, stock.model_dump())
        return StockInfo(id=stock_id, **stock.model_dump())


@app.get("/api/stocks/lookup/{isin}")
async def lookup_stock(isin: str):
    """Lookup stock information by ISIN via Yahoo Finance."""
    result = lookup_by_isin(isin)
    if result:
        return result
    raise HTTPException(status_code=404, detail=f"Could not find stock with ISIN {isin}")


@app.put("/api/stocks/{ticker}", response_model=StockInfo)
async def update_stock(ticker: str, stock: StockInfoCreate):
    """Update a stock."""
    with get_db() as conn:
        if not update_stock_info(conn, ticker, stock.model_dump()):
            raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")

        updated = get_stock_info(conn, ticker)
        return StockInfo(**updated)


@app.delete("/api/stocks/{ticker}")
async def remove_stock(ticker: str):
    """Delete a stock."""
    with get_db() as conn:
        if delete_stock_info(conn, ticker):
            return {"message": f"Stock {ticker} deleted"}
        raise HTTPException(status_code=404, detail=f"Stock {ticker} not found")


@app.get("/api/stocks/{ticker}")
async def get_stock_detail(ticker: str):
    """Get detailed information about a stock."""
    with get_db() as conn:
        info = get_stock_info(conn, ticker)
        transactions = get_all_transactions(conn, ticker)
        dividends = get_all_dividends(conn, ticker)
        price_info = get_current_price(ticker)

        return {
            "info": info,
            "transactions": transactions,
            "dividends": dividends,
            "current_price": price_info
        }


@app.get("/api/stocks/{ticker}/history")
async def get_stock_history(ticker: str, period: str = Query(default="1y", regex="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$")):
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

        # Get historical data from Yahoo Finance
        try:
            stock = yf.Ticker(ticker)
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
# Broker Endpoints
# =============================================================================

@app.get("/api/brokers", response_model=List[str])
async def get_brokers():
    """Get list of available brokers."""
    with get_db() as conn:
        return get_available_brokers(conn)


@app.post("/api/brokers")
async def create_broker(data: dict):
    """Create a new broker."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO broker_settings (broker_name) VALUES (?)",
            (data['broker_name'],)
        )
        conn.commit()
        return {"message": f"Broker {data['broker_name']} created"}


# =============================================================================
# Analysis Endpoints
# =============================================================================

@app.get("/api/analysis/performance", response_model=PerformanceSummary)
async def get_performance_summary():
    """Get portfolio performance summary including dividends."""
    with get_db() as conn:
        transactions = get_all_transactions(conn)
        dividends = get_all_dividends(conn)

        if not transactions:
            return PerformanceSummary(
                total_invested=0, current_value=0, total_gain_loss=0,
                total_gain_loss_percent=0, total_dividends=0,
                total_return=0, total_return_percent=0
            )

        # Group by ticker
        by_ticker = {}
        for tx in transactions:
            ticker = tx['ticker']
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(tx)

        usd_eur_rate = get_exchange_rate('USD', 'EUR')

        total_invested = 0
        total_current_value = 0
        ticker_performance = []

        for ticker, txs in by_ticker.items():
            price_info = get_current_price(ticker)
            current_price = price_info['current_price'] if price_info else None
            currency = price_info['currency'] if price_info else 'USD'
            exchange_rate = usd_eur_rate if currency == 'USD' else 1.0

            metrics = calculate_holding_metrics(txs, current_price, exchange_rate)

            if metrics['quantity'] > 0:
                total_invested += metrics['total_invested_eur']
                if metrics['current_value']:
                    total_current_value += metrics['current_value']
                    if metrics['gain_loss_percent'] is not None:
                        ticker_performance.append({
                            'ticker': ticker,
                            'name': txs[0]['name'],
                            'percent': metrics['gain_loss_percent']
                        })

        # Calculate dividends
        total_dividends = sum(d['net_amount'] or d['bruto_amount'] for d in dividends if d['received'])

        total_gain_loss = total_current_value - total_invested
        total_gain_loss_percent = (total_gain_loss / total_invested * 100) if total_invested > 0 else 0
        total_return = total_gain_loss + total_dividends
        total_return_percent = (total_return / total_invested * 100) if total_invested > 0 else 0

        # Best/worst performers
        best = max(ticker_performance, key=lambda x: x['percent']) if ticker_performance else None
        worst = min(ticker_performance, key=lambda x: x['percent']) if ticker_performance else None

        return PerformanceSummary(
            total_invested=round(total_invested, 2),
            current_value=round(total_current_value, 2),
            total_gain_loss=round(total_gain_loss, 2),
            total_gain_loss_percent=round(total_gain_loss_percent, 2),
            total_dividends=round(total_dividends, 2),
            total_return=round(total_return, 2),
            total_return_percent=round(total_return_percent, 2),
            best_performer=best['name'] if best else None,
            best_performer_percent=round(best['percent'], 2) if best else None,
            worst_performer=worst['name'] if worst else None,
            worst_performer_percent=round(worst['percent'], 2) if worst else None
        )


@app.get("/api/analysis/dividends", response_model=DividendSummary)
async def get_dividend_summary():
    """Get dividend analysis summary."""
    with get_db() as conn:
        dividends = get_all_dividends(conn)
        transactions = get_all_transactions(conn)

        if not dividends:
            return DividendSummary(
                total_received=0, total_withheld_tax=0, total_net=0,
                dividend_yield=0, by_ticker={}, by_year={}
            )

        total_received = 0
        total_withheld_tax = 0
        by_ticker = {}
        by_year = {}

        for div in dividends:
            if div['received']:
                net = div['net_amount'] or div['bruto_amount']
                total_received += div['bruto_amount']
                total_withheld_tax += div['withheld_tax']

                # By ticker
                ticker = div['ticker']
                if ticker not in by_ticker:
                    by_ticker[ticker] = {'total': 0, 'count': 0}
                by_ticker[ticker]['total'] += net
                by_ticker[ticker]['count'] += 1

                # By year
                year = str(div['ex_date'].year) if hasattr(div['ex_date'], 'year') else div['ex_date'][:4]
                if year not in by_year:
                    by_year[year] = 0
                by_year[year] += net

        total_net = total_received - total_withheld_tax

        # Calculate total invested for yield
        total_invested = sum(
            tx['quantity'] * tx['price_per_share'] * tx['exchange_rate']
            for tx in transactions if tx['transaction_type'] == 'BUY'
        )
        dividend_yield = (total_net / total_invested * 100) if total_invested > 0 else 0

        return DividendSummary(
            total_received=round(total_received, 2),
            total_withheld_tax=round(total_withheld_tax, 2),
            total_net=round(total_net, 2),
            dividend_yield=round(dividend_yield, 2),
            by_ticker=by_ticker,
            by_year=by_year
        )


@app.get("/api/analysis/costs", response_model=CostSummary)
async def get_cost_summary():
    """Get cost/fees analysis summary."""
    with get_db() as conn:
        transactions = get_all_transactions(conn)

        if not transactions:
            return CostSummary(
                total_fees=0, total_taxes=0, transaction_count=0,
                avg_fee_per_transaction=0, by_broker={}, fees_as_percent_of_invested=0
            )

        total_fees = 0
        total_taxes = 0
        total_invested = 0
        by_broker = {}

        for tx in transactions:
            total_fees += tx['fees']
            total_taxes += tx['taxes']

            if tx['transaction_type'] == 'BUY':
                total_invested += tx['quantity'] * tx['price_per_share'] * tx['exchange_rate']

            broker = tx['broker']
            if broker not in by_broker:
                by_broker[broker] = {'total': 0, 'count': 0}
            by_broker[broker]['total'] += tx['fees']
            by_broker[broker]['count'] += 1

        transaction_count = len(transactions)
        avg_fee = total_fees / transaction_count if transaction_count > 0 else 0
        fees_percent = (total_fees / total_invested * 100) if total_invested > 0 else 0

        return CostSummary(
            total_fees=round(total_fees, 2),
            total_taxes=round(total_taxes, 2),
            transaction_count=transaction_count,
            avg_fee_per_transaction=round(avg_fee, 2),
            by_broker=by_broker,
            fees_as_percent_of_invested=round(fees_percent, 2)
        )


@app.get("/api/analysis/allocation", response_model=AllocationSummary)
async def get_allocation_summary():
    """Get portfolio allocation by broker, country, and asset type."""
    with get_db() as conn:
        transactions = get_all_transactions(conn)

        if not transactions:
            return AllocationSummary(by_broker=[], by_country=[], by_asset_type=[])

        # Group by ticker
        by_ticker = {}
        for tx in transactions:
            ticker = tx['ticker']
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(tx)

        usd_eur_rate = get_exchange_rate('USD', 'EUR')

        broker_totals = {}
        country_totals = {}
        asset_type_totals = {}
        total_value = 0

        for ticker, txs in by_ticker.items():
            price_info = get_current_price(ticker)
            current_price = price_info['current_price'] if price_info else None
            currency = price_info['currency'] if price_info else 'USD'
            exchange_rate = usd_eur_rate if currency == 'USD' else 1.0

            metrics = calculate_holding_metrics(txs, current_price, exchange_rate)

            if metrics['quantity'] > 0 and metrics['current_value']:
                value = metrics['current_value']
                total_value += value

                # By broker
                broker = txs[0]['broker']
                broker_totals[broker] = broker_totals.get(broker, 0) + value

                # Get stock info for country/type
                stock_info = get_stock_info(conn, ticker)
                if stock_info:
                    country = stock_info['country']
                    asset_type = stock_info['asset_type']
                else:
                    country = 'Onbekend'
                    asset_type = 'STOCK'

                country_totals[country] = country_totals.get(country, 0) + value
                asset_type_totals[asset_type] = asset_type_totals.get(asset_type, 0) + value

        def to_allocation_items(totals: dict, total: float) -> List[AllocationItem]:
            items = []
            for name, value in sorted(totals.items(), key=lambda x: -x[1]):
                items.append(AllocationItem(
                    name=name,
                    value=round(value, 2),
                    percentage=round(value / total * 100, 2) if total > 0 else 0
                ))
            return items

        return AllocationSummary(
            by_broker=to_allocation_items(broker_totals, total_value),
            by_country=to_allocation_items(country_totals, total_value),
            by_asset_type=to_allocation_items(asset_type_totals, total_value)
        )


# =============================================================================
# User Settings Endpoints
# =============================================================================

@app.get("/api/settings", response_model=UserSettings)
async def get_settings():
    """Get user settings."""
    with get_db() as conn:
        settings = get_user_settings(conn)
        return UserSettings(
            date_format=settings.get('date_format', 'DD/MM/YYYY'),
            finnhub_api_key=settings.get('finnhub_api_key')
        )


@app.put("/api/settings", response_model=UserSettings)
async def save_settings(settings: UserSettings):
    """Update user settings."""
    with get_db() as conn:
        update_user_settings(conn, settings.model_dump())
        return settings


@app.post("/api/settings/test-finnhub")
async def test_finnhub_api():
    """Test Finnhub API connection by doing a simple quote lookup."""
    from .services.market_data import _get_finnhub_client

    client = _get_finnhub_client()
    if not client:
        raise HTTPException(status_code=400, detail="Geen Finnhub API key ingesteld")

    try:
        # Test with a simple quote lookup for Apple
        quote = client.quote('AAPL')
        if quote and quote.get('c'):
            return {
                "success": True,
                "message": "Finnhub API werkt correct!",
                "test_data": {
                    "ticker": "AAPL",
                    "price": quote.get('c'),
                    "change_percent": quote.get('dp')
                }
            }
        else:
            raise HTTPException(status_code=400, detail="Finnhub API antwoordde, maar data is ongeldig")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Finnhub API test mislukt: {str(e)}")


# =============================================================================
# Manual Price Endpoints
# =============================================================================

@app.get("/api/stocks/{ticker}/prices", response_model=List[ManualPrice])
async def get_stock_prices(ticker: str):
    """Get all manual prices for a stock."""
    with get_db() as conn:
        prices = get_manual_prices(conn, ticker)
        return [ManualPrice(**p) for p in prices]


@app.post("/api/stocks/{ticker}/prices", response_model=ManualPrice)
async def add_stock_price(ticker: str, price: ManualPriceCreate):
    """Add a manual price for a stock."""
    with get_db() as conn:
        price_data = price.model_dump()
        price_data['ticker'] = ticker
        price_id = insert_manual_price(conn, price_data)
        return ManualPrice(id=price_id, **price_data)


@app.put("/api/stocks/{ticker}/prices/{price_id}", response_model=ManualPrice)
async def edit_stock_price(ticker: str, price_id: int, price: ManualPriceCreate):
    """Update a manual price."""
    with get_db() as conn:
        price_data = price.model_dump()
        if not update_manual_price(conn, price_id, price_data):
            raise HTTPException(status_code=404, detail="Price not found")
        return ManualPrice(id=price_id, **price_data)


@app.delete("/api/stocks/{ticker}/prices/{price_id}")
async def remove_stock_price(ticker: str, price_id: int):
    """Delete a manual price."""
    with get_db() as conn:
        if delete_manual_price(conn, price_id):
            return {"message": "Price deleted"}
        raise HTTPException(status_code=404, detail="Price not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
