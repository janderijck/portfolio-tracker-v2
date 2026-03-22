"""
Portfolio router - portfolio holdings, price status, and movers endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List
from ..models import PortfolioHolding, PortfolioSummary, PortfolioResponse, MoverItem
from ..services.database import (
    get_db, get_all_transactions, get_stock_info, get_all_stocks,
    get_all_saxo_price_cache, get_latest_manual_price, get_portfolio_holdings,
)
from ..services.market_data import (
    get_current_price, get_exchange_rate, get_cached_price_only,
    get_price_cache_status, refresh_all_prices, get_period_changes,
)
from ..services.calculations import calculate_holding_metrics

router = APIRouter(prefix="/api", tags=["portfolio"])

PERIOD_MAP = {'1w': '5d', '1m': '1mo', 'ytd': 'ytd', '1y': '1y'}


@router.get("/portfolio", response_model=PortfolioResponse)
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
                elif stock_info_data and stock_info_data.get('asset_type') == 'FUND':
                    isin = stock_info_data.get('isin') or (transactions[0]['isin'] if transactions else None)
                    if isin:
                        price_info = get_cached_price_only(isin)
                        if price_info:
                            current_price = price_info['current_price']
                            currency = price_info['currency']
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

                    saxo_cached = saxo_prices.get(ticker)
                    if saxo_cached and saxo_cached.get('saxo_price'):
                        current_price = saxo_cached['saxo_price']
                        currency = saxo_cached.get('currency', currency)

                # Get change_percent from price cache
                change_pct = None
                if not uses_manual:
                    pi = get_cached_price_only(price_ticker)
                    if pi:
                        change_pct = pi.get('change_percent')

                price_cache[ticker] = {
                    'current_price': current_price,
                    'currency': currency,
                    'manual_price_date': manual_price_date,
                    'pays_dividend': pays_dividend,
                    'change_percent': change_pct,
                }
            else:
                cached = price_cache[ticker]
                current_price = cached['current_price']
                currency = cached['currency']
                manual_price_date = cached['manual_price_date']
                pays_dividend = cached['pays_dividend']
                change_pct = cached['change_percent']

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
                pays_dividend=pays_dividend
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


@router.get("/prices/status")
async def prices_status():
    """Get price cache status."""
    return get_price_cache_status()


@router.post("/prices/refresh")
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


@router.get("/movers", response_model=List[MoverItem])
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
