"""
Portfolio Tracker API - Main application.

Routes only - business logic is in services.
"""
import logging
import os
from datetime import datetime, timedelta
from io import BytesIO
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .models import (
    Transaction, TransactionCreate, Dividend, DividendCreate,
    PortfolioHolding, PortfolioSummary, PortfolioResponse,
    StockInfo, StockInfoCreate, MoverItem,
    PerformanceSummary, DividendSummary, CostSummary, AllocationSummary, AllocationItem,
    UserSettings, ManualPrice, ManualPriceCreate,
    SaxoPosition, SaxoBalance, SaxoSyncResult, SaxoDividendSyncResult,
    SaxoImportRequest, SaxoImportResult, SaxoConfig,
    DividendForecastItem, MonthlyDividendSummary, DividendCalendarResponse,
    BrokerDetail, BrokerCashBalance, BrokerCashUpdate, BrokerAccountTypeUpdate, BrokerCashItem, CashSummary,
    IBKRConfig, IBKRSyncResult, IBKRStatus,
    TelegramConfig, StockAlert, StockAlertCreate, AlertCheckResult,
)
from .services.database import (
    get_db,
    insert_transaction, get_all_transactions, update_transaction, delete_transaction,
    insert_dividend, get_all_dividends, update_dividend, delete_dividend,
    get_stock_info, get_all_stocks, insert_stock_info, update_stock_info, delete_stock_info,
    get_available_brokers, get_broker_settings, update_broker_cash, search_stocks,
    get_broker_cash_balances, upsert_broker_cash_balance, update_broker_account_type,
    get_user_settings, update_user_settings,
    insert_manual_price, get_manual_prices, get_latest_manual_price, delete_manual_price, update_manual_price,
    clear_all_data,
    get_stocks_missing_yahoo_ticker, update_stock_yahoo_ticker,
    get_saxo_token, save_saxo_token,
    get_saxo_tokens, save_saxo_tokens, clear_saxo_tokens,
    get_saxo_price_cache, save_saxo_price_cache, get_all_saxo_price_cache,
    get_saxo_config, save_saxo_config,
    get_portfolio_holdings,
    get_ibkr_config, save_ibkr_config, clear_ibkr_config, update_ibkr_last_sync,
    check_source_id_exists, insert_cash_transaction,
    get_telegram_config, save_telegram_config, clear_telegram_config,
    get_alerts_for_stock, get_all_enabled_alerts, insert_alert, update_alert, delete_alert,
)
from .services.market_data import (
    get_current_price, get_exchange_rate, lookup_by_isin, get_dividend_history,
    openfigi_map_isin, openfigi_search, resolve_yahoo_ticker_from_isin,
    get_dividend_info, get_fund_price, get_cached_price_only,
    get_price_cache_status, refresh_all_prices,
    get_historical_monthly_prices, get_historical_exchange_rates,
    get_period_changes,
)
from .services.dividend_forecast import (
    detect_dividend_frequency, estimate_next_dividend_amount, project_future_ex_dates,
)
from .services.calculations import calculate_holding_metrics

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: start and stop the alert scheduler."""
    from .services.alert_checker import check_all_alerts

    scheduler.add_job(check_all_alerts, "interval", hours=1, id="alert_checker")
    scheduler.start()
    logging.getLogger(__name__).info("Alert scheduler started (interval: 1 hour)")
    yield
    scheduler.shutdown()


app = FastAPI(
    title="Portfolio Tracker API",
    description="API for tracking stock portfolio and dividends",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
# Get frontend URL from environment variable (for Azure deployment)
frontend_url = os.getenv("FRONTEND_URL", "")
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5177",
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

        # Group transactions by (ticker, broker) so each broker has separate holdings
        by_ticker_broker = {}
        for tx in all_transactions:
            key = (tx['ticker'], tx['broker'])
            if key not in by_ticker_broker:
                by_ticker_broker[key] = []
            by_ticker_broker[key].append(tx)

        # Get current exchange rate
        usd_eur_rate = get_exchange_rate('USD', 'EUR')

        # Load all broker cached prices once
        saxo_prices = get_all_saxo_price_cache(conn)

        # Pre-resolve prices per ticker (avoid duplicate lookups for same ticker across brokers)
        price_cache = {}

        holdings = []
        total_invested_eur = 0
        total_current_value_eur = 0

        for (ticker, broker), transactions in by_ticker_broker.items():
            # Resolve price once per ticker
            if ticker not in price_cache:
                stock_info_data = get_stock_info(conn, ticker)
                uses_manual = stock_info_data and stock_info_data.get('manual_price_tracking')
                pays_dividend = stock_info_data.get('pays_dividend', False) if stock_info_data else False
                manual_price_date = None
                price_ticker = (stock_info_data.get('yahoo_ticker') or ticker) if stock_info_data else ticker

                price_updated_at = None
                if uses_manual:
                    saxo_cached = saxo_prices.get(ticker)
                    if saxo_cached and saxo_cached.get('saxo_price'):
                        current_price = saxo_cached['saxo_price']
                        currency = saxo_cached.get('currency', transactions[0]['currency'])
                    else:
                        manual_price = get_latest_manual_price(conn, ticker)
                        if manual_price:
                            current_price = manual_price['price']
                            currency = manual_price['currency']
                            manual_price_date = manual_price['date']
                        else:
                            price_info = get_cached_price_only(price_ticker)
                            current_price = price_info['current_price'] if price_info else None
                            currency = price_info['currency'] if price_info else transactions[0]['currency']
                            if price_info:
                                price_updated_at = price_info.get('updated_at')
                elif stock_info_data and stock_info_data.get('asset_type') == 'FUND':
                    isin = stock_info_data.get('isin') or (transactions[0]['isin'] if transactions else None)
                    if isin:
                        price_info = get_cached_price_only(isin)
                        if price_info:
                            current_price = price_info['current_price']
                            currency = price_info['currency']
                            price_updated_at = price_info.get('updated_at')
                        else:
                            manual_price = get_latest_manual_price(conn, ticker)
                            if manual_price:
                                current_price = manual_price['price']
                                currency = manual_price['currency']
                                manual_price_date = manual_price['date']
                            else:
                                current_price = None
                                currency = transactions[0]['currency'] if transactions else 'EUR'
                    else:
                        current_price = None
                        currency = transactions[0]['currency'] if transactions else 'EUR'
                else:
                    price_info = get_cached_price_only(price_ticker)
                    current_price = price_info['current_price'] if price_info else None
                    currency = price_info['currency'] if price_info else 'USD'
                    if price_info:
                        price_updated_at = price_info.get('updated_at')

                    saxo_cached = saxo_prices.get(ticker)
                    if saxo_cached and saxo_cached.get('saxo_price'):
                        current_price = saxo_cached['saxo_price']
                        currency = saxo_cached.get('currency', currency)

                # Get change_percent from price cache
                # Only use change_percent if the cache is recent (< 18h)
                # to avoid showing stale daily changes from days ago
                change_pct = None
                if not uses_manual:
                    # For funds, price is cached under ISIN, not price_ticker
                    change_lookup = price_ticker
                    if stock_info_data and stock_info_data.get('asset_type') == 'FUND':
                        change_lookup = stock_info_data.get('isin') or (transactions[0]['isin'] if transactions else price_ticker)
                    pi = get_cached_price_only(change_lookup)
                    if pi:
                        pi_updated = pi.get('updated_at')
                        if pi_updated:
                            try:
                                cache_age = datetime.now() - datetime.fromisoformat(pi_updated)
                                if cache_age < timedelta(hours=18):
                                    change_pct = pi.get('change_percent')
                            except (ValueError, TypeError):
                                pass

                price_cache[ticker] = {
                    'current_price': current_price,
                    'currency': currency,
                    'manual_price_date': manual_price_date,
                    'pays_dividend': pays_dividend,
                    'change_percent': change_pct,
                    'price_updated_at': price_updated_at,
                }
            else:
                cached = price_cache[ticker]
                current_price = cached['current_price']
                currency = cached['currency']
                manual_price_date = cached['manual_price_date']
                pays_dividend = cached['pays_dividend']
                change_pct = cached['change_percent']
                price_updated_at = cached['price_updated_at']

            # Calculate metrics using pure functions
            tx_currency = transactions[0]['currency'] if transactions else 'EUR'
            cp = current_price
            cur = currency
            if cur == 'USD' and tx_currency == 'EUR' and cp is not None:
                cp = round(cp * usd_eur_rate, 4)
                cur = 'EUR'
            exchange_rate = usd_eur_rate if cur == 'USD' else 1.0
            metrics = calculate_holding_metrics(transactions, cp, exchange_rate)

            # Skip if no quantity held
            if metrics['quantity'] < 0.0001:
                continue

            first_tx = transactions[0]

            if metrics['current_value'] is not None:
                if metrics['is_usd_account']:
                    current_value_eur = round(metrics['current_value'] * exchange_rate, 2)
                else:
                    current_value_eur = round(metrics['current_value'], 2)
            else:
                current_value_eur = None

            holding = PortfolioHolding(
                ticker=ticker,
                isin=first_tx['isin'],
                name=first_tx['name'],
                broker=broker,
                quantity=metrics['quantity'],
                avg_purchase_price=metrics['avg_purchase_price'],
                total_invested=metrics['total_invested'],
                total_invested_eur=metrics['total_invested_eur'],
                total_fees=metrics['total_fees'],
                currency=first_tx['currency'],
                current_price=metrics['current_price'],
                current_value=metrics['current_value'],
                current_value_eur=current_value_eur,
                gain_loss=metrics['gain_loss'],
                gain_loss_percent=metrics['gain_loss_percent'],
                change_percent=round(change_pct, 2) if change_pct is not None else None,
                is_usd_account=metrics['is_usd_account'],
                manual_price_date=manual_price_date,
                pays_dividend=pays_dividend,
                price_updated_at=price_updated_at
            )
            holdings.append(holding)

            total_invested_eur += metrics['total_invested_eur']
            if metrics['current_value']:
                if metrics['is_usd_account']:
                    total_current_value_eur += metrics['current_value'] * exchange_rate
                else:
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

        # Get price cache status for timestamp
        cache_status = get_price_cache_status()

        return PortfolioResponse(
            holdings=holdings,
            summary=summary,
            prices_updated_at=cache_status.get('newest_update'),
        )


# =============================================================================
# Price Refresh Endpoints
# =============================================================================

@app.get("/api/prices/status")
async def prices_status():
    """Get price cache status."""
    return get_price_cache_status()


@app.post("/api/prices/refresh")
async def prices_refresh():
    """Force-refresh all prices from external sources (Yahoo/Finnhub/Morningstar)."""
    with get_db() as conn:
        all_transactions = get_all_transactions(conn)
        if not all_transactions:
            return {"refreshed": 0, "total": 0, "errors": []}

        # Build list of unique tickers with their price info
        seen = set()
        holdings_info = []
        for tx in all_transactions:
            ticker = tx['ticker']
            if ticker in seen:
                continue
            seen.add(ticker)

            stock_info_data = get_stock_info(conn, ticker)
            if stock_info_data and stock_info_data.get('manual_price_tracking'):
                continue  # Skip manual-tracked stocks

            price_ticker = (stock_info_data.get('yahoo_ticker') or ticker) if stock_info_data else ticker
            asset_type = stock_info_data.get('asset_type', 'STOCK') if stock_info_data else 'STOCK'
            isin = stock_info_data.get('isin', '') if stock_info_data else tx.get('isin', '')

            holdings_info.append({
                'ticker': ticker,
                'price_ticker': price_ticker,
                'asset_type': asset_type,
                'isin': isin,
            })

    return refresh_all_prices(holdings_info)


# =============================================================================
# Movers Endpoints
# =============================================================================

PERIOD_MAP = {'1w': '5d', '1m': '1mo', 'ytd': 'ytd', '1y': '1y'}


@app.get("/api/movers", response_model=List[MoverItem])
async def get_movers(period: str = Query(..., pattern="^(1w|1m|ytd|1y)$")):
    """
    Get price changes over a period for all held stocks.
    Skips FUNDs and manual_price_tracking stocks.
    """
    yf_period = PERIOD_MAP[period]

    with get_db() as conn:
        holdings = get_portfolio_holdings(conn)
        all_stocks = get_all_stocks(conn)

    stock_map = {s['ticker']: s for s in all_stocks}

    # Build yahoo_ticker map, skipping FUND and manual_price_tracking
    yahoo_tickers = {}
    name_map = {}
    for h in holdings:
        ticker = h['ticker']
        info = stock_map.get(ticker)
        if not info:
            continue
        if info.get('asset_type') == 'FUND':
            continue
        if info.get('manual_price_tracking'):
            continue
        yahoo_sym = info.get('yahoo_ticker') or ticker
        yahoo_tickers[ticker] = yahoo_sym
        name_map[ticker] = h.get('name', ticker)

    changes = get_period_changes(yahoo_tickers, yf_period)

    result = []
    for ticker, change_pct in changes.items():
        result.append(MoverItem(
            ticker=ticker,
            name=name_map.get(ticker, ticker),
            change_percent=round(change_pct, 2),
        ))

    return result


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
        fields = set(Dividend.model_fields.keys())
        return [Dividend(**{k: v for k, v in div.items() if k in fields}) for div in dividends]


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


@app.get("/api/dividends/calendar", response_model=DividendCalendarResponse)
async def get_dividend_calendar():
    """
    Get dividend calendar with historical dividends and forecasted future dividends.
    Forecasts are calculated on-the-fly based on yfinance data.
    """
    from datetime import date as date_type, datetime, timedelta
    from collections import defaultdict

    with get_db() as conn:
        # 1. Historical dividends (last 12 months)
        all_dividends = get_all_dividends(conn)
        twelve_months_ago = (date_type.today() - timedelta(days=365)).isoformat()
        historical = [
            Dividend(**div) for div in all_dividends
            if div['ex_date'] >= twelve_months_ago
        ]

        # 2. Get holdings with positive quantity
        holdings = get_portfolio_holdings(conn)

        # 3. Build forecasts per holding
        forecasted: List[DividendForecastItem] = []

        for holding in holdings:
            ticker = holding['ticker']
            stock_info_data = get_stock_info(conn, ticker)

            if not stock_info_data or not stock_info_data.get('pays_dividend'):
                continue

            yahoo_ticker = stock_info_data.get('yahoo_ticker') or ticker
            div_info = get_dividend_info(yahoo_ticker)
            if not div_info:
                continue

            hist_divs = div_info.get('historical_dividends', [])
            if not hist_divs:
                continue

            # Extract dates and amounts
            hist_dates = []
            hist_amounts = []
            for hd in hist_divs:
                try:
                    hist_dates.append(date_type.fromisoformat(hd['date']))
                    hist_amounts.append(hd['amount'])
                except (ValueError, KeyError):
                    continue

            if not hist_dates:
                continue

            frequency = detect_dividend_frequency(hist_dates)
            per_share = estimate_next_dividend_amount(
                hist_amounts,
                div_info.get('dividend_rate'),
                frequency,
            )

            if per_share <= 0:
                continue

            last_ex = max(hist_dates)
            future_dates = project_future_ex_dates(last_ex, frequency, 12)

            total_qty = holding['total_quantity']
            isin = stock_info_data.get('isin', '')
            currency = div_info.get('currency', 'USD')

            stock_name = stock_info_data.get('name')

            for fd in future_dates:
                forecasted.append(DividendForecastItem(
                    ticker=ticker,
                    isin=isin,
                    ex_date=fd,
                    estimated_amount=round(per_share * total_qty, 2),
                    currency=currency,
                    frequency=frequency,
                    is_forecast=True,
                    stock_name=stock_name,
                ))

        # 4. Build monthly summary (12 months back + 12 months forward)
        monthly: dict[str, dict] = defaultdict(lambda: {'received': 0.0, 'forecasted': 0.0})

        for div in historical:
            month_key = str(div.ex_date)[:7]
            net = div.net_amount if div.net_amount is not None else (div.bruto_amount - div.withheld_tax)
            monthly[month_key]['received'] += net

        for fc in forecasted:
            month_key = fc.ex_date.isoformat()[:7]
            monthly[month_key]['forecasted'] += fc.estimated_amount

        monthly_summary = sorted(
            [
                MonthlyDividendSummary(
                    month=month,
                    received=round(data['received'], 2),
                    forecasted=round(data['forecasted'], 2),
                )
                for month, data in monthly.items()
            ],
            key=lambda x: x.month,
        )

        return DividendCalendarResponse(
            historical=historical,
            forecasted=sorted(forecasted, key=lambda x: x.ex_date),
            monthly_summary=monthly_summary,
        )


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


@app.get("/api/stocks/search")
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
                except Exception:
                    pass  # Non-critical

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
            except Exception:
                pass

        # 3. Morningstar for ISIN fund searches (always try for ISINs)
        if len(q) >= 2:
            query_upper = q.upper()
            is_isin = len(query_upper) == 12 and query_upper[:2].isalpha()
            if is_isin:
                try:
                    from .services.morningstar import search_fund_by_isin
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
                except Exception:
                    pass

        # 4. Combine: local first, then external (deduplicate on ticker)
        local_tickers = {r['ticker'] for r in local_results}
        combined = local_results + [e for e in external_results if e['ticker'] not in local_tickers]

        return combined


@app.post("/api/stocks/enrich")
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
            except Exception:
                pass  # Don't fail stock detail if forecast fails

        # Fetch social sentiment (non-critical)
        sentiment = None
        try:
            from .services.stocktwits import get_sentiment
            sentiment = get_sentiment(ticker)
        except Exception:
            pass

        return {
            "info": info,
            "transactions": transactions,
            "dividends": dividends,
            "current_price": price_info,
            "upcoming_dividends": upcoming_dividends,
            "sentiment": sentiment,
        }


@app.get("/api/stocks/{ticker}/history")
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
                from .services.morningstar import get_fund_nav_history
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


@app.get("/api/brokers/details", response_model=List[BrokerDetail])
async def get_broker_details():
    """Get all brokers with their details including cash balances."""
    with get_db() as conn:
        brokers = get_broker_settings(conn)
        all_cash = get_broker_cash_balances(conn)

        # Group cash balances by broker
        cash_by_broker = {}
        for cb in all_cash:
            cash_by_broker.setdefault(cb['broker_name'], []).append(
                BrokerCashBalance(currency=cb['currency'], balance=cb['balance'])
            )

        return [
            BrokerDetail(
                broker_name=b['broker_name'],
                country=b.get('country', 'België'),
                has_w8ben=bool(b.get('has_w8ben', 0)),
                w8ben_expiry_date=b.get('w8ben_expiry_date'),
                cash_balances=cash_by_broker.get(b['broker_name'], []),
                account_type=b.get('account_type', 'Privé'),
                notes=b.get('notes'),
            )
            for b in brokers
        ]


@app.put("/api/brokers/{broker_name}/account-type")
async def update_broker_account_type_endpoint(broker_name: str, data: BrokerAccountTypeUpdate):
    """Update account type for a broker."""
    with get_db() as conn:
        broker = get_broker_settings(conn, broker_name)
        if not broker:
            raise HTTPException(status_code=404, detail=f"Broker {broker_name} not found")
        update_broker_account_type(conn, broker_name, data.account_type)
        return {"message": f"Account type voor {broker_name} bijgewerkt naar {data.account_type}"}


@app.put("/api/brokers/{broker_name}/cash")
async def update_broker_cash_endpoint(broker_name: str, data: BrokerCashUpdate):
    """Update cash balance for a broker (upsert; removes row if balance=0)."""
    with get_db() as conn:
        broker = get_broker_settings(conn, broker_name)
        if not broker:
            raise HTTPException(status_code=404, detail=f"Broker {broker_name} not found")
        upsert_broker_cash_balance(conn, broker_name, data.currency, data.balance)
        return {"message": f"Cash saldo voor {broker_name} ({data.currency}) bijgewerkt"}


@app.get("/api/brokers/cash-summary", response_model=CashSummary)
async def get_cash_summary():
    """Get total cash across all brokers in EUR."""
    with get_db() as conn:
        all_cash = get_broker_cash_balances(conn)
        per_broker = []
        total_cash_eur = 0.0

        for cb in all_cash:
            balance = cb['balance']
            currency = cb['currency']

            if balance == 0:
                continue

            if currency == 'EUR':
                cash_eur = balance
            else:
                rate = get_exchange_rate(currency, 'EUR')
                cash_eur = balance * rate

            per_broker.append(BrokerCashItem(
                broker_name=cb['broker_name'],
                cash_balance=balance,
                cash_currency=currency,
                cash_balance_eur=round(cash_eur, 2),
            ))
            total_cash_eur += cash_eur

        return CashSummary(
            total_cash_eur=round(total_cash_eur, 2),
            per_broker=per_broker,
        )


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
            stock_info_data = get_stock_info(conn, ticker)
            price_ticker = (stock_info_data.get('yahoo_ticker') or ticker) if stock_info_data else ticker
            price_info = get_current_price(price_ticker)
            current_price = price_info['current_price'] if price_info else None
            currency = price_info['currency'] if price_info else 'USD'
            exchange_rate = usd_eur_rate if currency == 'USD' else 1.0

            metrics = calculate_holding_metrics(txs, current_price, exchange_rate)

            if metrics['quantity'] >= 0.0001:
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
            stock_info = get_stock_info(conn, ticker)
            price_ticker = (stock_info.get('yahoo_ticker') or ticker) if stock_info else ticker
            price_info = get_current_price(price_ticker)
            current_price = price_info['current_price'] if price_info else None
            currency = price_info['currency'] if price_info else 'USD'
            exchange_rate = usd_eur_rate if currency == 'USD' else 1.0

            metrics = calculate_holding_metrics(txs, current_price, exchange_rate)

            if metrics['quantity'] >= 0.0001 and metrics['current_value']:
                value = metrics['current_value']
                total_value += value

                # By broker
                broker = txs[0]['broker']
                broker_totals[broker] = broker_totals.get(broker, 0) + value
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
# Portfolio Evolution
# =============================================================================

@app.get("/api/analysis/portfolio-evolution")
async def get_portfolio_evolution(broker: Optional[str] = Query(None)):
    """Get monthly portfolio evolution using historical prices from Yahoo Finance."""
    from collections import defaultdict
    from datetime import datetime as dt

    with get_db() as conn:
        all_transactions = get_all_transactions(conn)

        if not all_transactions:
            return []

        # Filter out KP (Kapitaalpremie) entries - insurance accounting, not real trades
        transactions = [tx for tx in all_transactions if not (tx.get('notes') or '').startswith(('Creatie KP', 'Aftrek KP'))]

        # Filter by broker if specified
        if broker:
            transactions = [tx for tx in transactions if tx['broker'] == broker]

        if not transactions:
            return []

        # Current exchange rate as fallback
        usd_eur_rate = get_exchange_rate('USD', 'EUR')
        saxo_prices = get_all_saxo_price_cache(conn)

        # Classify tickers: yahoo-fetchable vs manual/fund
        by_ticker = defaultdict(list)
        for tx in transactions:
            by_ticker[tx['ticker']].append(tx)

        yahoo_tickers = {}       # {internal_ticker: yahoo_symbol}
        fund_isins = {}          # {internal_ticker: isin} for Morningstar history
        ticker_currency = {}     # {internal_ticker: currency}
        current_price_eur = {}   # fallback current prices in EUR
        has_usd_tickers = False

        for ticker, txs in by_ticker.items():
            stock_info_data = get_stock_info(conn, ticker)
            uses_manual = stock_info_data and stock_info_data.get('manual_price_tracking')
            price_ticker = (stock_info_data.get('yahoo_ticker') or ticker) if stock_info_data else ticker

            cur_price = None
            currency = txs[0]['currency']

            if uses_manual:
                # Manual tracking: use saxo/manual price as current, no historical
                saxo_cached = saxo_prices.get(ticker)
                if saxo_cached and saxo_cached.get('saxo_price'):
                    cur_price = saxo_cached['saxo_price']
                    currency = saxo_cached.get('currency', currency)
                else:
                    manual_price = get_latest_manual_price(conn, ticker)
                    if manual_price:
                        cur_price = manual_price['price']
                        currency = manual_price['currency']
            elif stock_info_data and stock_info_data.get('asset_type') == 'FUND':
                # Fund: queue for Morningstar historical fetch
                isin = stock_info_data.get('isin') or (txs[0].get('isin') if txs else None)
                if isin:
                    fund_isins[ticker] = isin
                    price_info = get_cached_price_only(isin)
                    if price_info:
                        cur_price = price_info['current_price']
                        currency = price_info['currency']
                if cur_price is None:
                    manual_price = get_latest_manual_price(conn, ticker)
                    if manual_price:
                        cur_price = manual_price['price']
                        currency = manual_price['currency']
            else:
                # Yahoo-fetchable: queue for historical fetch
                yahoo_tickers[ticker] = price_ticker
                # Get cached current price as fallback
                price_info = get_cached_price_only(price_ticker)
                if price_info:
                    cur_price = price_info['current_price']
                    currency = price_info['currency']
                saxo_cached = saxo_prices.get(ticker)
                if saxo_cached and saxo_cached.get('saxo_price'):
                    cur_price = saxo_cached['saxo_price']
                    currency = saxo_cached.get('currency', currency)

            ticker_currency[ticker] = currency
            if currency == 'USD':
                has_usd_tickers = True

            # Convert current price to EUR for fallback
            if cur_price is not None and currency == 'USD':
                current_price_eur[ticker] = cur_price * usd_eur_rate
            else:
                current_price_eur[ticker] = cur_price

        # Determine date range
        first_date = min(tx['date'] for tx in transactions)

        # Fetch historical monthly prices from Yahoo Finance
        hist_prices = get_historical_monthly_prices(yahoo_tickers, first_date)

        # Fetch historical fund prices from Morningstar
        if fund_isins:
            from .services.morningstar import get_fund_nav_history
            for ticker, isin in fund_isins.items():
                nav_history = get_fund_nav_history(isin, 'max')
                if nav_history:
                    # Convert daily data to monthly (last price per month)
                    monthly = {}
                    for point in nav_history:
                        month_key = point['date'][:7]
                        monthly[month_key] = point['price']
                    hist_prices[ticker] = monthly

        # Fetch historical USD->EUR rates if needed
        hist_usd_eur = {}
        if has_usd_tickers:
            hist_usd_eur = get_historical_exchange_rates('USD', 'EUR', first_date)

        def get_price_eur(ticker: str, month: str) -> Optional[float]:
            """Get price in EUR for a ticker in a specific month."""
            # Try historical price first (for yahoo-fetchable tickers)
            hist = hist_prices.get(ticker, {})
            price = hist.get(month)

            if price is not None:
                # Convert USD to EUR using historical rate
                if ticker_currency.get(ticker) == 'USD':
                    rate = hist_usd_eur.get(month, usd_eur_rate)
                    return price * rate
                return price

            # Fallback to current price
            return current_price_eur.get(ticker)

        # Build monthly events
        events = []
        for tx in transactions:
            month_key = tx['date'][:7]
            events.append((month_key, tx))
        events.sort(key=lambda e: e[1]['date'])

        # Track running state per ticker
        ticker_qty = defaultdict(float)
        ticker_invested = defaultdict(float)

        # Group events by month in order
        month_order = []
        month_events = defaultdict(list)
        for month_key, tx in events:
            if month_key not in month_events:
                month_order.append(month_key)
            month_events[month_key].append(tx)

        # Generate all months from first transaction to current month
        current_month = dt.now().strftime('%Y-%m')
        all_months = []
        y, m = int(month_order[0][:4]), int(month_order[0][5:7])
        while True:
            mo = f'{y:04d}-{m:02d}'
            if mo > current_month:
                break
            all_months.append(mo)
            m += 1
            if m > 12:
                m = 1
                y += 1

        result = []
        for month in all_months:
            # Process any transactions in this month
            if month in month_events:
                for tx in month_events[month]:
                    ticker = tx['ticker']
                    qty = tx['quantity']
                    tx_rate = tx.get('exchange_rate', 1.0)
                    if tx['currency'] == 'USD' and tx_rate == 1.0:
                        fx = hist_usd_eur.get(month, usd_eur_rate)
                        cost_eur = qty * tx['price_per_share'] * fx
                    else:
                        cost_eur = qty * tx['price_per_share'] * tx_rate
                    if tx['transaction_type'] == 'BUY':
                        ticker_qty[ticker] += qty
                        ticker_invested[ticker] += cost_eur
                    elif tx['transaction_type'] == 'SELL':
                        if ticker_qty[ticker] > 0:
                            sell_ratio = min(qty / ticker_qty[ticker], 1.0)
                            ticker_invested[ticker] *= (1 - sell_ratio)
                        ticker_qty[ticker] = max(0, ticker_qty[ticker] - qty)

            # Skip months before any positions exist
            if not any(q > 0.0001 for q in ticker_qty.values()):
                continue

            # Calculate portfolio value with historical prices
            total_invested = sum(ticker_invested.values())
            total_value = 0.0
            has_any_price = False
            for ticker, qty in ticker_qty.items():
                if qty <= 0.0001:
                    continue
                price = get_price_eur(ticker, month)
                if price is not None:
                    total_value += qty * price
                    has_any_price = True

            if has_any_price:
                result.append({
                    "date": month,
                    "gain": round(total_value - total_invested, 2),
                    "invested": round(total_invested, 2),
                    "value": round(total_value, 2),
                })

        return result


# =============================================================================
# User Settings Endpoints
# =============================================================================

@app.get("/api/settings", response_model=UserSettings)
async def get_settings():
    """Get user settings."""
    with get_db() as conn:
        settings = get_user_settings(conn)
        saxo_token = settings.get('saxo_access_token')
        return UserSettings(
            date_format=settings.get('date_format', 'DD/MM/YYYY'),
            finnhub_api_key=settings.get('finnhub_api_key'),
            openfigi_api_key=settings.get('openfigi_api_key'),
            saxo_connected=bool(saxo_token),
        )


@app.put("/api/settings", response_model=UserSettings)
async def save_settings(settings: UserSettings):
    """Update user settings."""
    with get_db() as conn:
        # Only update non-Saxo settings (Saxo tokens managed via OAuth)
        update_user_settings(conn, {
            'date_format': settings.date_format,
            'finnhub_api_key': settings.finnhub_api_key,
            'openfigi_api_key': settings.openfigi_api_key,
        })
        return settings


@app.delete("/api/database/reset")
async def reset_database():
    """Delete all data (transactions, dividends, stocks, caches) but keep settings and brokers."""
    with get_db() as conn:
        clear_all_data(conn)
        return {"message": "Alle gegevens zijn gewist"}


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
# Saxo Integration Endpoints
# =============================================================================

@app.get("/api/saxo/config", response_model=SaxoConfig)
async def get_saxo_config_endpoint():
    """Get Saxo API configuration."""
    with get_db() as conn:
        config = get_saxo_config(conn)
        return SaxoConfig(**config) if config else SaxoConfig()


@app.put("/api/saxo/config", response_model=SaxoConfig)
async def save_saxo_config_endpoint(config: SaxoConfig):
    """Save Saxo API configuration."""
    with get_db() as conn:
        save_saxo_config(
            conn,
            config.client_id,
            config.client_secret,
            config.redirect_uri,
            config.auth_url,
            config.token_url,
        )
        # Clear existing tokens when config changes
        clear_saxo_tokens(conn)
        return config


@app.get("/api/saxo/auth-url")
async def get_saxo_auth_url():
    """Return authorization URL for Saxo OAuth flow."""
    import secrets
    from .services.saxo import get_auth_url

    with get_db() as conn:
        config = get_saxo_config(conn)
    if not config.get("client_id"):
        raise HTTPException(status_code=400, detail="Saxo configuratie ontbreekt. Stel eerst Client ID, Secret en Redirect URI in.")

    state = secrets.token_urlsafe(32)
    url = get_auth_url(config, state)
    return {"url": url, "state": state}


@app.post("/api/saxo/callback")
async def saxo_oauth_callback(body: dict):
    """Exchange authorization code for tokens."""
    from .services.saxo import exchange_code_for_tokens, SaxoClient
    from datetime import datetime, timedelta

    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Geen authorization code ontvangen")

    try:
        with get_db() as conn:
            config = get_saxo_config(conn)
            if not config.get("client_id"):
                raise HTTPException(status_code=400, detail="Saxo configuratie ontbreekt")

            tokens = exchange_code_for_tokens(config, code)
            expiry = datetime.now() + timedelta(seconds=tokens["expires_in"])

            save_saxo_tokens(
                conn,
                tokens["access_token"],
                tokens.get("refresh_token", ""),
                expiry.isoformat(),
            )

            # Test connection
            client = SaxoClient(tokens["access_token"], config)
            account_info = client.test_connection()

        return {
            "success": True,
            "message": "Saxo verbinding succesvol!",
            "account": account_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth token exchange mislukt: {str(e)}")


@app.post("/api/saxo/disconnect")
async def saxo_disconnect():
    """Clear all Saxo tokens."""
    with get_db() as conn:
        clear_saxo_tokens(conn)
    return {"success": True, "message": "Saxo ontkoppeld"}


@app.post("/api/saxo/test")
async def test_saxo_connection():
    """Test Saxo connection using stored OAuth token."""
    from .services.saxo import SaxoClient, get_valid_token

    with get_db() as conn:
        token = get_valid_token(conn)
        if not token:
            raise HTTPException(status_code=400, detail="Geen Saxo verbinding. Koppel eerst via OAuth.")
        config = get_saxo_config(conn)

    try:
        client = SaxoClient(token, config)
        account_info = client.test_connection()
        return {
            "success": True,
            "message": "Saxo verbinding succesvol!",
            "account": account_info,
        }
    except Exception as e:
        status_code = getattr(getattr(e, 'response', None), 'status_code', 500)
        if status_code == 401:
            detail = "Token is verlopen. Koppel opnieuw via Saxo OAuth."
        else:
            detail = f"Saxo API fout: {str(e)}"
        raise HTTPException(status_code=400, detail=detail)


@app.get("/api/saxo/positions")
async def get_saxo_positions():
    """Fetch Saxo positions and match with local stocks."""
    from .services.saxo import SaxoClient, match_positions_with_local, get_valid_token

    with get_db() as conn:
        token = get_valid_token(conn)
        if not token:
            raise HTTPException(status_code=400, detail="Geen Saxo verbinding")
        config = get_saxo_config(conn)

        try:
            client = SaxoClient(token, config)
            positions = client.get_positions()

            # Get instrument details for ISIN matching
            uics = [p["uic"] for p in positions if p.get("uic")]
            asset_types = {p["asset_type"] for p in positions if p.get("asset_type")}
            instruments = client.get_instrument_details(uics, asset_types) if uics else []

            # Match with local stocks
            local_stocks = get_all_stocks(conn)
            enriched = match_positions_with_local(positions, instruments, local_stocks)

            result = []
            for pos in enriched:
                result.append(SaxoPosition(
                    uic=pos["uic"],
                    isin=pos.get("isin"),
                    name=pos.get("description", pos.get("symbol", "")),
                    quantity=pos["amount"],
                    current_price=pos["current_price"],
                    current_value=pos["market_value"],
                    currency=pos["currency"],
                    pnl=pos.get("pnl"),
                    pnl_percent=pos.get("pnl_percent"),
                    matched_ticker=pos.get("matched_ticker"),
                    symbol=pos.get("instrument_symbol") or pos.get("symbol"),
                    exchange_id=pos.get("exchange_id"),
                ))

            return result

        except Exception as e:
            status_code = getattr(getattr(e, 'response', None), 'status_code', 500)
            if status_code == 401:
                raise HTTPException(status_code=401, detail="Saxo token verlopen")
            raise HTTPException(status_code=500, detail=f"Fout bij ophalen posities: {str(e)}")


@app.get("/api/saxo/balances")
async def get_saxo_balances():
    """Fetch Saxo account balances."""
    from .services.saxo import SaxoClient, get_valid_token

    with get_db() as conn:
        token = get_valid_token(conn)
        if not token:
            raise HTTPException(status_code=400, detail="Geen Saxo verbinding")
        config = get_saxo_config(conn)

    try:
        client = SaxoClient(token, config)
        balances = client.get_balances()
        return SaxoBalance(**balances)
    except Exception as e:
        status_code = getattr(getattr(e, 'response', None), 'status_code', 500)
        if status_code == 401:
            raise HTTPException(status_code=401, detail="Saxo token verlopen")
        raise HTTPException(status_code=500, detail=f"Fout bij ophalen saldi: {str(e)}")


@app.post("/api/saxo/sync", response_model=SaxoSyncResult)
async def sync_saxo():
    """Full sync: fetch positions, match with local DB, cache Saxo prices, sync dividends."""
    from .services.saxo import SaxoClient, match_positions_with_local, get_valid_token, process_saxo_dividends

    with get_db() as conn:
        token = get_valid_token(conn)
        if not token:
            raise HTTPException(status_code=400, detail="Geen Saxo verbinding")
        config = get_saxo_config(conn)

        try:
            client = SaxoClient(token, config)

            # 1. Fetch positions and balances
            positions = client.get_positions()
            balances = client.get_balances()

            # 2. Fetch instrument details for ISIN
            uics = [p["uic"] for p in positions if p.get("uic")]
            asset_types = {p["asset_type"] for p in positions if p.get("asset_type")}
            instruments = client.get_instrument_details(uics, asset_types) if uics else []

            # 3. Match with local stocks
            local_stocks = get_all_stocks(conn)
            enriched = match_positions_with_local(positions, instruments, local_stocks)

            # 4. Cache Saxo prices for matched positions
            matched_count = 0
            unmatched_count = 0
            saxo_position_models = []

            for pos in enriched:
                ticker = pos.get("matched_ticker")
                if ticker:
                    matched_count += 1
                    # Cache the Saxo price for this ticker
                    save_saxo_price_cache(
                        conn, ticker,
                        pos["current_price"],
                        pos.get("pnl_percent", 0),
                        pos["currency"],
                    )
                else:
                    unmatched_count += 1

                saxo_position_models.append(SaxoPosition(
                    uic=pos["uic"],
                    isin=pos.get("isin"),
                    name=pos.get("description", pos.get("symbol", "")),
                    quantity=pos["amount"],
                    current_price=pos["current_price"],
                    current_value=pos["market_value"],
                    currency=pos["currency"],
                    pnl=pos.get("pnl"),
                    pnl_percent=pos.get("pnl_percent"),
                    matched_ticker=ticker,
                    symbol=pos.get("instrument_symbol") or pos.get("symbol"),
                    exchange_id=pos.get("exchange_id"),
                ))

            # Fetch transactions once for dividend sync and missing local detection
            all_transactions = get_all_transactions(conn)

            # 4b. Dividend sync
            dividend_result = SaxoDividendSyncResult()
            try:
                ca_events, ca_available = client.get_corporate_action_events("Past")
                if ca_available and not ca_events:
                    # Endpoint works but no past events, try active
                    ca_events, _ = client.get_corporate_action_events("Active")

                if not ca_available:
                    # CA endpoint not available (403/404), try fallback
                    dividend_result.ca_endpoint_available = False
                    ca_events, _ = client.get_dividend_transactions()

                if ca_events:
                    existing_dividends = get_all_dividends(conn)
                    new_dividends, div_stats = process_saxo_dividends(
                        ca_events, enriched, local_stocks,
                        existing_dividends, all_transactions,
                    )
                    dividend_result.skipped_duplicate = div_stats["skipped_duplicate"]
                    dividend_result.skipped_unmatched = div_stats["skipped_unmatched"]

                    for div_data in new_dividends:
                        try:
                            insert_dividend(conn, div_data)
                            dividend_result.imported += 1
                        except Exception as e:
                            dividend_result.errors.append(f"{div_data.get('ticker', '?')}: {str(e)}")
            except Exception as e:
                logging.error(f"Dividend sync failed (non-fatal): {e}")
                dividend_result.errors.append(f"Dividend sync mislukt: {str(e)}")

            # 5. Detect local Saxo stocks missing from Saxo positions
            saxo_isins = {pos.get("isin") for pos in enriched if pos.get("isin")}
            local_saxo_stocks = [
                s for s in local_stocks
                if s.get("isin") and s["isin"] in {stock["isin"] for stock in local_stocks}
            ]
            # Count local stocks with broker=Saxo that are not in Saxo positions
            saxo_tickers = set()
            for tx in all_transactions:
                if tx.get("broker", "").lower() == "saxo":
                    saxo_tickers.add(tx["ticker"])
            local_saxo_isins = set()
            for stock in local_stocks:
                if stock["ticker"] in saxo_tickers and stock.get("isin"):
                    local_saxo_isins.add(stock["isin"])
            missing_local = len(local_saxo_isins - saxo_isins)

            return SaxoSyncResult(
                positions=saxo_position_models,
                balance=SaxoBalance(**balances),
                matched=matched_count,
                unmatched=unmatched_count,
                missing_local=missing_local,
                dividends=dividend_result,
            )

        except Exception as e:
            status_code = getattr(getattr(e, 'response', None), 'status_code', 500)
            if status_code == 401:
                raise HTTPException(status_code=401, detail="Saxo token verlopen")
            raise HTTPException(status_code=500, detail=f"Fout bij synchronisatie: {str(e)}")


@app.post("/api/saxo/import-positions", response_model=SaxoImportResult)
async def import_saxo_positions(request: SaxoImportRequest):
    """Import unmatched Saxo positions as local stocks with initial BUY transactions."""
    from .services.saxo import resolve_ticker_from_saxo, resolve_country_from_isin
    from datetime import date as date_today

    with get_db() as conn:
        imported_stocks = 0
        imported_transactions = 0
        skipped = 0
        errors = []

        # Ensure Saxo broker exists
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO broker_settings (broker_name) VALUES (?)",
            ("Saxo",)
        )
        conn.commit()

        for pos in request.positions:
            try:
                # Check if stock already exists for this ISIN
                if pos.isin:
                    existing = None
                    all_stocks = get_all_stocks(conn)
                    for s in all_stocks:
                        if s.get("isin") == pos.isin:
                            existing = s
                            break
                    if existing:
                        skipped += 1
                        continue

                # Resolve ticker
                app_ticker, yahoo_ticker = resolve_ticker_from_saxo(
                    pos.symbol or "", pos.isin or ""
                )

                # Resolve country from ISIN
                country = resolve_country_from_isin(pos.isin or "")

                # Calculate average buy price from PnL
                if pos.pnl is not None and pos.quantity > 0:
                    avg_buy_price = (pos.current_value - pos.pnl) / pos.quantity
                elif pos.pnl_percent is not None and pos.pnl_percent != 0:
                    avg_buy_price = pos.current_price / (1 + pos.pnl_percent / 100)
                else:
                    avg_buy_price = pos.current_price

                avg_buy_price = round(avg_buy_price, 4)

                # If no yahoo_ticker found, enable manual price tracking
                # so Saxo price is used instead of Yahoo Finance lookup
                needs_manual = yahoo_ticker is None

                # Insert stock_info
                insert_stock_info(conn, {
                    "ticker": app_ticker,
                    "isin": pos.isin or "",
                    "name": pos.name,
                    "asset_type": "STOCK",
                    "country": country,
                    "yahoo_ticker": yahoo_ticker,
                    "manual_price_tracking": needs_manual,
                    "pays_dividend": False,
                })
                imported_stocks += 1

                # For manual tracking stocks: save Saxo current_price as initial manual price
                if needs_manual and pos.current_price and pos.current_price > 0:
                    insert_manual_price(conn, {
                        "ticker": app_ticker,
                        "date": date_today.today().isoformat(),
                        "price": pos.current_price,
                        "currency": pos.currency,
                    })

                # Insert initial BUY transaction
                insert_transaction(conn, {
                    "date": date_today.today().isoformat(),
                    "broker": "Saxo",
                    "transaction_type": "BUY",
                    "name": pos.name,
                    "ticker": app_ticker,
                    "isin": pos.isin or "",
                    "quantity": pos.quantity,
                    "price_per_share": avg_buy_price,
                    "currency": pos.currency,
                    "fees": 0,
                    "taxes": 0,
                    "exchange_rate": 1.0,
                    "fees_currency": pos.currency,
                    "notes": "Geïmporteerd vanuit Saxo positie",
                })
                imported_transactions += 1

            except Exception as e:
                errors.append(f"{pos.name}: {str(e)}")

        return SaxoImportResult(
            imported_stocks=imported_stocks,
            imported_transactions=imported_transactions,
            skipped=skipped,
            errors=errors,
        )


@app.get("/api/saxo/status")
async def get_saxo_status():
    """Get Saxo connection status and last sync time."""
    with get_db() as conn:
        token = get_saxo_token(conn)
        saxo_cache = get_all_saxo_price_cache(conn)

        # Find the most recent cache update
        last_sync = None
        if saxo_cache:
            last_sync = max(
                (v.get("updated_at") for v in saxo_cache.values() if v.get("updated_at")),
                default=None,
            )

        return {
            "connected": bool(token),
            "has_token": bool(token),
            "cached_prices": len(saxo_cache),
            "last_sync": last_sync,
        }


@app.get("/api/saxo/debug-raw")
async def debug_saxo_raw():
    """Temporary: return raw Saxo API responses for debugging field names."""
    from .services.saxo import SaxoClient, get_valid_token

    with get_db() as conn:
        token = get_valid_token(conn)
        if not token:
            raise HTTPException(status_code=400, detail="Geen Saxo verbinding")
        config = get_saxo_config(conn)

    try:
        client = SaxoClient(token, config)
        raw_positions = client.get_raw_positions()
        first_position = raw_positions.get("Data", [{}])[0] if raw_positions.get("Data") else {}

        # Get UICs for instrument details
        uics = [p.get("PositionBase", {}).get("Uic") for p in raw_positions.get("Data", []) if p.get("PositionBase", {}).get("Uic")]
        asset_types = {p.get("PositionBase", {}).get("AssetType") for p in raw_positions.get("Data", []) if p.get("PositionBase", {}).get("AssetType")}
        raw_instruments = client.get_raw_instrument_details(uics, asset_types) if uics else {}
        first_instrument = raw_instruments.get("Data", [{}])[0] if raw_instruments.get("Data") else {}

        return {
            "positions_count": len(raw_positions.get("Data", [])),
            "first_position": first_position,
            "first_position_keys": {
                "top_level": list(first_position.keys()) if first_position else [],
                "PositionBase": list(first_position.get("PositionBase", {}).keys()) if first_position else [],
                "PositionView": list(first_position.get("PositionView", {}).keys()) if first_position else [],
                "DisplayAndFormat": list(first_position.get("DisplayAndFormat", {}).keys()) if first_position else [],
            },
            "instruments_count": len(raw_instruments.get("Data", [])),
            "first_instrument": first_instrument,
            "first_instrument_keys": list(first_instrument.keys()) if first_instrument else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug fout: {str(e)}")


# =============================================================================
# IBKR Integration Endpoints
# =============================================================================

@app.get("/api/ibkr/config")
async def get_ibkr_config_endpoint():
    """Get IBKR Flex Query configuration."""
    with get_db() as conn:
        config = get_ibkr_config(conn)
        return IBKRConfig(
            flex_token=config.get("flex_token", ""),
            query_id=config.get("query_id", ""),
        )


@app.put("/api/ibkr/config")
async def save_ibkr_config_endpoint(config: IBKRConfig):
    """Save IBKR Flex Query configuration."""
    with get_db() as conn:
        save_ibkr_config(conn, config.flex_token, config.query_id)
        return config


@app.post("/api/ibkr/test")
async def test_ibkr_connection():
    """Test IBKR connection by fetching a report."""
    from .services.ibkr import IBKRClient

    with get_db() as conn:
        config = get_ibkr_config(conn)

    if not config.get("flex_token") or not config.get("query_id"):
        raise HTTPException(status_code=400, detail="IBKR Flex Token en Query ID zijn vereist")

    try:
        client = IBKRClient(config["flex_token"], config["query_id"])
        account_info = client.test_connection()
        return {
            "success": True,
            "message": "IBKR verbinding succesvol!",
            "account": account_info,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"IBKR verbinding mislukt: {str(e)}")


@app.post("/api/ibkr/sync", response_model=IBKRSyncResult)
async def sync_ibkr():
    """Full IBKR sync: fetch report, parse trades/dividends/cash, import with dedup."""
    from .services.ibkr import IBKRClient, build_stocks_from_positions, resolve_ibkr_ticker
    from datetime import datetime

    with get_db() as conn:
        config = get_ibkr_config(conn)

    if not config.get("flex_token") or not config.get("query_id"):
        raise HTTPException(status_code=400, detail="IBKR niet geconfigureerd")

    result = IBKRSyncResult()

    try:
        client = IBKRClient(config["flex_token"], config["query_id"])
        statement = client.fetch_report()

        # 1. Extract positions + ISIN lookup
        positions, isin_lookup = client.get_positions(statement)
        result.positions_found = len(positions)

        # 2. Parse data
        trades = client.parse_trades(statement)
        dividends = client.parse_dividends(statement, isin_lookup)
        cash_txs = client.parse_cash_transactions(statement)

        with get_db() as conn:
            # 3. Ensure broker "IBKR" exists
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO broker_settings (broker_name) VALUES (?)",
                ("IBKR",)
            )
            conn.commit()

            # 4. Auto-create stock_info for new positions
            stocks_data = build_stocks_from_positions(positions, isin_lookup)
            existing_stocks = get_all_stocks(conn)
            existing_tickers = {s["ticker"] for s in existing_stocks}
            existing_isins = {s["isin"] for s in existing_stocks if s.get("isin")}

            for stock in stocks_data:
                # Skip if ticker or ISIN already exists
                if stock["ticker"] in existing_tickers:
                    continue
                if stock["isin"] and stock["isin"] in existing_isins:
                    continue
                try:
                    insert_stock_info(conn, stock)
                    existing_tickers.add(stock["ticker"])
                    if stock["isin"]:
                        existing_isins.add(stock["isin"])
                    result.stocks_created += 1
                except Exception as e:
                    result.warnings.append(f"Stock {stock['ticker']}: {str(e)}")

            # 4b. Resolve Yahoo tickers for newly created stocks via ISIN
            for stock in stocks_data:
                if stock["isin"] and stock["ticker"] in existing_tickers:
                    stock_info_data = get_stock_info(conn, stock["ticker"])
                    if stock_info_data and not stock_info_data.get("yahoo_ticker") and not stock_info_data.get("manual_price_tracking"):
                        try:
                            yahoo_ticker = resolve_yahoo_ticker_from_isin(stock["isin"])
                            if yahoo_ticker:
                                update_stock_yahoo_ticker(conn, stock["ticker"], yahoo_ticker)
                        except Exception:
                            pass

            # 5. Build ticker resolution map (IBKR symbol → app ticker)
            # For trades/dividends where symbol might not match our stock_info ticker
            ticker_map: dict[str, str] = {}
            for stock in existing_stocks:
                if stock.get("isin"):
                    # Map ISIN to our ticker
                    for ibkr_symbol, isin in isin_lookup.items():
                        if isin == stock["isin"]:
                            ticker_map[ibkr_symbol] = stock["ticker"]

            # 6. Import trades with dedup
            for trade in trades:
                source_id = trade.get("source_id")
                if source_id and check_source_id_exists(conn, "transactions", source_id):
                    continue

                # Resolve ticker
                ibkr_symbol = trade["ticker"]
                resolved_ticker = ticker_map.get(ibkr_symbol, ibkr_symbol)
                trade["ticker"] = resolved_ticker

                # Also resolve name from stock_info
                stock_info_data = get_stock_info(conn, resolved_ticker)
                if stock_info_data and stock_info_data.get("name"):
                    trade["name"] = stock_info_data["name"]

                try:
                    insert_transaction(conn, trade)
                    result.transactions_imported += 1
                except Exception as e:
                    result.errors.append(f"Trade {trade.get('ticker', '?')}: {str(e)}")

            # 6b. Create synthetic BUY transactions for positions without trades
            imported_tickers = set()
            for trade in trades:
                ibkr_symbol = trade.get("ticker", "")
                resolved = ticker_map.get(ibkr_symbol, ibkr_symbol)
                imported_tickers.add(resolved)

            # Also check which tickers already have transactions in the DB
            all_existing_txs = get_all_transactions(conn)
            tickers_with_txs = {tx["ticker"] for tx in all_existing_txs}

            for pos in positions:
                symbol = pos["symbol"]
                isin = pos.get("isin", "")
                resolved = ticker_map.get(symbol, symbol)

                if resolved in imported_tickers or resolved in tickers_with_txs:
                    continue

                # Look up stock_info for name
                stock_info_data = get_stock_info(conn, resolved)
                name = (stock_info_data or {}).get("name", pos.get("description", symbol))

                # Prefer cost basis (real avg purchase price) over mark price
                cost_basis = pos.get("cost_basis_price")
                price = cost_basis if cost_basis else (pos.get("mark_price") or 0.0)
                source_id = f"IBKR-POS-{symbol}"

                if check_source_id_exists(conn, "transactions", source_id):
                    continue

                price_note = "kostprijs uit IBKR" if cost_basis else "huidige koers, geen kostprijs beschikbaar"

                synthetic_tx = {
                    "date": datetime.now().date().isoformat(),
                    "broker": "IBKR",
                    "transaction_type": "BUY",
                    "name": name,
                    "ticker": resolved,
                    "isin": isin,
                    "quantity": pos["quantity"],
                    "price_per_share": price,
                    "currency": pos.get("currency", "USD"),
                    "fees": 0.0,
                    "taxes": 0.0,
                    "exchange_rate": 1.0,
                    "fees_currency": pos.get("currency", "USD"),
                    "notes": f"Synthetische transactie uit IBKR positie ({price_note})",
                    "source_id": source_id,
                }
                try:
                    insert_transaction(conn, synthetic_tx)
                    result.transactions_imported += 1
                    imported_tickers.add(resolved)
                    result.warnings.append(
                        f"{resolved}: synthetische BUY aangemaakt ({price_note})"
                    )
                except Exception as e:
                    result.errors.append(f"Synthetische tx {resolved}: {str(e)}")

            # 7. Import dividends with dedup
            for div in dividends:
                source_id = div.get("source_id")
                if source_id and check_source_id_exists(conn, "dividends", source_id):
                    continue

                # Resolve ticker
                ibkr_symbol = div["ticker"]
                resolved_ticker = ticker_map.get(ibkr_symbol, ibkr_symbol)
                div["ticker"] = resolved_ticker

                # Resolve ISIN from stock_info if not present
                if not div.get("isin"):
                    stock_info_data = get_stock_info(conn, resolved_ticker)
                    if stock_info_data:
                        div["isin"] = stock_info_data.get("isin", "")

                try:
                    insert_dividend(conn, div)
                    result.dividends_imported += 1
                except Exception as e:
                    result.errors.append(f"Dividend {div.get('ticker', '?')}: {str(e)}")

            # 8. Import cash transactions with dedup
            for cash in cash_txs:
                source_id = cash.get("source_id")
                if source_id and check_source_id_exists(conn, "cash_transactions", source_id):
                    continue

                try:
                    insert_cash_transaction(conn, cash)
                    result.cash_imported += 1
                except Exception as e:
                    result.errors.append(f"Cash {cash.get('date', '?')}: {str(e)}")

            # 9. Update last sync timestamp
            update_ibkr_last_sync(conn, datetime.now().isoformat())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"IBKR sync mislukt: {str(e)}")

    return result


@app.post("/api/ibkr/disconnect")
async def ibkr_disconnect():
    """Clear IBKR configuration."""
    with get_db() as conn:
        clear_ibkr_config(conn)
    return {"success": True, "message": "IBKR ontkoppeld"}


@app.get("/api/ibkr/status", response_model=IBKRStatus)
async def get_ibkr_status():
    """Get IBKR configuration status."""
    with get_db() as conn:
        config = get_ibkr_config(conn)
        has_token = bool(config.get("flex_token"))
        has_query_id = bool(config.get("query_id"))
        return IBKRStatus(
            configured=has_token and has_query_id,
            has_token=has_token,
            has_query_id=has_query_id,
            last_sync=config.get("last_sync"),
        )


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


# =============================================================================
# Import Endpoints
# =============================================================================

@app.post("/api/import/upload")
async def upload_import_file(
    file: UploadFile = File(...),
    broker: Optional[str] = Form(None),
):
    """
    Upload a broker export file for parsing.
    Returns parsed preview data without importing.
    """
    from .services.parsers import detect_broker, get_parser
    from dataclasses import asdict

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Geen bestand opgegeven")

    # Auto-detect broker if not specified
    detected_broker = broker or detect_broker(file.filename)
    if not detected_broker:
        raise HTTPException(
            status_code=400,
            detail="Kan broker niet detecteren. Selecteer de broker handmatig."
        )

    # Get parser
    try:
        parser = get_parser(detected_broker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in parser.supported_extensions():
        raise HTTPException(
            status_code=400,
            detail=f"Bestandstype {ext} wordt niet ondersteund. Verwacht: {', '.join(parser.supported_extensions())}"
        )

    # Parse
    content = await file.read()
    try:
        result = parser.parse(BytesIO(content), file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fout bij het parsen: {str(e)}")

    # Auto-resolve Yahoo tickers via ISIN (OpenFIGI)
    for stock in result.stocks:
        if not stock.yahoo_ticker and stock.isin:
            try:
                yahoo_ticker = resolve_yahoo_ticker_from_isin(stock.isin)
                if yahoo_ticker:
                    stock.yahoo_ticker = yahoo_ticker
                    stock.ticker = yahoo_ticker
            except Exception:
                pass  # Gebruiker kan handmatig invullen in preview

    # Update transactie-tickers die als ISIN staan naar resolved ticker
    isin_to_ticker = {s.isin: s.ticker for s in result.stocks if s.yahoo_ticker}
    for tx in result.transactions:
        if tx.ticker in isin_to_ticker:
            tx.ticker = isin_to_ticker[tx.ticker]

    # Check for duplicates
    with get_db() as conn:
        existing_transactions = get_all_transactions(conn)
        existing_dividends = get_all_dividends(conn)

        # Build lookup sets for duplicate detection
        tx_lookup = set()
        for tx in existing_transactions:
            key = (str(tx['date']), tx['ticker'], tx['transaction_type'],
                   str(tx['quantity']), str(round(tx['price_per_share'], 2)))
            tx_lookup.add(key)

        div_lookup = set()
        for div in existing_dividends:
            key = (str(div['ex_date']), div['ticker'],
                   str(round(div['bruto_amount'], 2)))
            div_lookup.add(key)

        # Mark duplicates
        for tx in result.transactions:
            key = (tx.date, tx.ticker, tx.transaction_type,
                   str(tx.quantity), str(round(tx.price_per_share, 2)))
            if key in tx_lookup:
                tx.is_duplicate = True

        for div in result.dividends:
            key = (div.ex_date, div.ticker,
                   str(round(div.bruto_amount, 2)))
            if key in div_lookup:
                div.is_duplicate = True

    # Convert to dict for JSON response
    return {
        "broker": result.broker,
        "transactions": [asdict(t) for t in result.transactions],
        "dividends": [asdict(d) for d in result.dividends],
        "cash_transactions": [asdict(c) for c in result.cash_transactions],
        "stocks": [asdict(s) for s in result.stocks],
        "warnings": result.warnings,
        "skipped_rows": result.skipped_rows,
        "summary": {
            "total_transactions": len(result.transactions),
            "total_dividends": len(result.dividends),
            "total_cash": len(result.cash_transactions),
            "total_stocks": len(result.stocks),
            "duplicate_transactions": sum(1 for t in result.transactions if t.is_duplicate),
            "duplicate_dividends": sum(1 for d in result.dividends if d.is_duplicate),
        }
    }


@app.post("/api/import/confirm")
async def confirm_import(data: dict):
    """
    Confirm and execute the import of parsed data.
    Expects: { transactions: [...], dividends: [...], cash_transactions: [...], stocks: [...] }
    """
    from .services.database import (
        insert_transaction, insert_dividend, insert_cash_transaction,
        insert_stock_info, get_stock_info
    )

    with get_db() as conn:
        imported = {
            "transactions": 0,
            "dividends": 0,
            "cash_transactions": 0,
            "stocks": 0,
        }
        errors = []

        # 1. Import stocks first (so transactions can reference them)
        for stock in data.get("stocks", []):
            existing = get_stock_info(conn, stock["ticker"])
            if not existing:
                try:
                    insert_stock_info(conn, {
                        "ticker": stock["ticker"],
                        "isin": stock.get("isin", ""),
                        "name": stock.get("name", stock["ticker"]),
                        "asset_type": stock.get("asset_type", "STOCK"),
                        "country": stock.get("country", "Onbekend"),
                        "yahoo_ticker": stock.get("yahoo_ticker"),
                        "manual_price_tracking": stock.get("manual_price_tracking", False),
                        "pays_dividend": False,
                    })
                    imported["stocks"] += 1
                except Exception as e:
                    errors.append(f"Effect {stock.get('ticker', '?')}: {str(e)}")

        # 1b. Enrich stocks missing yahoo_ticker via ISIN lookup
        for stock in data.get("stocks", []):
            if not stock.get("yahoo_ticker") and stock.get("isin"):
                stock_info_data = get_stock_info(conn, stock["ticker"])
                if stock_info_data and stock_info_data.get("manual_price_tracking"):
                    continue  # Skip manual-tracked stocks
                try:
                    yahoo_ticker = resolve_yahoo_ticker_from_isin(stock["isin"])
                    if yahoo_ticker:
                        update_stock_yahoo_ticker(conn, stock["ticker"], yahoo_ticker)
                except Exception:
                    pass  # Non-critical, can be enriched later

        # 2. Ensure broker(s) exist
        broker_names = set()
        for tx in data.get("transactions", []):
            if tx.get("broker"):
                broker_names.add(tx["broker"])
        for cash in data.get("cash_transactions", []):
            if cash.get("broker"):
                broker_names.add(cash["broker"])
        if broker_names:
            cursor = conn.cursor()
            for broker_name in broker_names:
                cursor.execute(
                    "INSERT OR IGNORE INTO broker_settings (broker_name) VALUES (?)",
                    (broker_name,)
                )
            conn.commit()

        # 3. Import transactions
        for tx in data.get("transactions", []):
            try:
                tx_data = {
                    "date": tx["date"],
                    "broker": tx.get("broker", "Onbekend"),
                    "transaction_type": tx["transaction_type"],
                    "name": tx["name"],
                    "ticker": tx["ticker"],
                    "isin": tx.get("isin", ""),
                    "quantity": tx["quantity"],
                    "price_per_share": tx["price_per_share"],
                    "currency": tx.get("currency", "EUR"),
                    "fees": tx.get("fees", 0),
                    "taxes": tx.get("taxes", 0),
                    "exchange_rate": tx.get("exchange_rate", 1.0),
                    "fees_currency": tx.get("fees_currency", "EUR"),
                    "notes": tx.get("notes"),
                }
                insert_transaction(conn, tx_data)
                imported["transactions"] += 1
            except Exception as e:
                errors.append(f"Transactie {tx.get('ticker', '?')} ({tx.get('date', '?')}): {str(e)}")

        # 4. Import dividends
        for div in data.get("dividends", []):
            try:
                div_data = {
                    "ticker": div["ticker"],
                    "isin": div.get("isin", ""),
                    "ex_date": div["ex_date"],
                    "bruto_amount": div["bruto_amount"],
                    "currency": div.get("currency", "EUR"),
                    "withheld_tax": div.get("withheld_tax", 0),
                    "net_amount": div.get("net_amount"),
                    "received": div.get("received", True),
                    "notes": div.get("notes"),
                }
                insert_dividend(conn, div_data)
                imported["dividends"] += 1
            except Exception as e:
                errors.append(f"Dividend {div.get('ticker', '?')} ({div.get('ex_date', '?')}): {str(e)}")

        # 5. Import cash transactions
        for cash in data.get("cash_transactions", []):
            try:
                cash_data = {
                    "date": cash["date"],
                    "broker": cash.get("broker", "Onbekend"),
                    "transaction_type": cash["transaction_type"],
                    "amount": cash["amount"],
                    "currency": cash.get("currency", "EUR"),
                    "source_amount": cash.get("source_amount"),
                    "source_currency": cash.get("source_currency"),
                    "exchange_rate": cash.get("exchange_rate"),
                    "notes": cash.get("notes"),
                }
                insert_cash_transaction(conn, cash_data)
                imported["cash_transactions"] += 1
            except Exception as e:
                errors.append(f"Cashbeweging {cash.get('date', '?')}: {str(e)}")

        return {
            "message": "Import voltooid" if not errors else f"Import voltooid met {len(errors)} fout(en)",
            "imported": imported,
            "errors": errors,
        }


# =============================================================================
# Telegram & Alert Endpoints
# =============================================================================

@app.get("/api/telegram/config")
async def get_telegram_config_endpoint():
    """Get Telegram configuration."""
    with get_db() as conn:
        config = get_telegram_config(conn)
        return TelegramConfig(
            bot_token=config.get("bot_token", ""),
            chat_id=config.get("chat_id", ""),
        )


@app.put("/api/telegram/config")
async def save_telegram_config_endpoint(config: TelegramConfig):
    """Save Telegram configuration."""
    with get_db() as conn:
        save_telegram_config(conn, config.bot_token, config.chat_id)
        return config


@app.post("/api/telegram/test")
async def test_telegram():
    """Send a test message via Telegram."""
    from .services.telegram import test_telegram_connection

    with get_db() as conn:
        config = get_telegram_config(conn)

    bot_token = config.get("bot_token", "")
    chat_id = config.get("chat_id", "")

    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram bot token en chat ID zijn vereist")

    result = test_telegram_connection(bot_token, chat_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/api/telegram/disconnect")
async def disconnect_telegram():
    """Clear Telegram configuration."""
    with get_db() as conn:
        clear_telegram_config(conn)
    return {"success": True, "message": "Telegram ontkoppeld"}


@app.get("/api/alerts/{ticker}")
async def get_stock_alerts(ticker: str):
    """Get all alerts for a stock."""
    with get_db() as conn:
        alerts = get_alerts_for_stock(conn, ticker)
        return [StockAlert(**a) for a in alerts]


@app.post("/api/alerts", response_model=StockAlert)
async def create_alert(alert: StockAlertCreate):
    """Create a new stock alert."""
    # Validate: period required for period alerts, threshold for price alerts
    if alert.alert_type in ("period_high", "period_low"):
        if not alert.period:
            raise HTTPException(
                status_code=400,
                detail="Periode is vereist voor period alerts (52w, 26w, 13w)"
            )
    elif alert.alert_type in ("above", "below"):
        if alert.threshold_price is None:
            raise HTTPException(
                status_code=400,
                detail="Drempelprijs is vereist voor prijs alerts"
            )

    with get_db() as conn:
        alert_id = insert_alert(conn, alert.model_dump())
        return StockAlert(id=alert_id, **alert.model_dump())


@app.put("/api/alerts/{alert_id}", response_model=StockAlert)
async def update_alert_endpoint(alert_id: int, alert: StockAlertCreate):
    """Update an existing alert."""
    with get_db() as conn:
        if not update_alert(conn, alert_id, alert.model_dump()):
            raise HTTPException(status_code=404, detail="Alert niet gevonden")
        return StockAlert(id=alert_id, **alert.model_dump())


@app.delete("/api/alerts/{alert_id}")
async def delete_alert_endpoint(alert_id: int):
    """Delete an alert."""
    with get_db() as conn:
        if delete_alert(conn, alert_id):
            return {"message": "Alert verwijderd"}
        raise HTTPException(status_code=404, detail="Alert niet gevonden")


@app.post("/api/alerts/check", response_model=AlertCheckResult)
async def manual_check_alerts():
    """Manually trigger an alert check (for testing)."""
    from .services.alert_checker import check_all_alerts

    result = check_all_alerts()
    return AlertCheckResult(**result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
