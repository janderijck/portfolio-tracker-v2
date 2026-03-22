"""
Analysis router - performance, dividends, costs, allocation, and portfolio evolution endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from ..models import (
    PerformanceSummary, DividendSummary, CostSummary, AllocationSummary, AllocationItem,
)
from ..services.database import (
    get_db, get_all_transactions, get_all_dividends, get_stock_info,
    get_all_saxo_price_cache, get_latest_manual_price, get_portfolio_holdings,
    get_all_stocks,
)
from ..services.market_data import (
    get_current_price, get_exchange_rate, get_cached_price_only,
    get_fund_price, get_historical_monthly_prices, get_historical_exchange_rates,
)
from ..services.calculations import calculate_holding_metrics

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/performance", response_model=PerformanceSummary)
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


@router.get("/dividends", response_model=DividendSummary)
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


@router.get("/costs", response_model=CostSummary)
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


@router.get("/allocation", response_model=AllocationSummary)
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


@router.get("/portfolio-evolution")
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
            from ..services.morningstar import get_fund_nav_history
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
