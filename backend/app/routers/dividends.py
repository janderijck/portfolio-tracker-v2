from fastapi import APIRouter, HTTPException
from typing import List, Optional
from ..models import (
    Dividend, DividendCreate, DividendForecastItem, MonthlyDividendSummary, DividendCalendarResponse
)
from ..services.database import (
    get_db, get_all_dividends, insert_dividend, update_dividend, delete_dividend,
    get_all_transactions, get_stock_info, get_portfolio_holdings,
)
from ..services.market_data import get_dividend_info, get_dividend_history
from ..services.dividend_forecast import detect_dividend_frequency, estimate_next_dividend_amount, project_future_ex_dates

router = APIRouter(prefix="/api", tags=["dividends"])


@router.get("/dividends", response_model=List[Dividend])
async def get_dividends(ticker: Optional[str] = None):
    """Get all dividends, optionally filtered by ticker."""
    with get_db() as conn:
        dividends = get_all_dividends(conn, ticker)
        fields = set(Dividend.model_fields.keys())
        return [Dividend(**{k: v for k, v in div.items() if k in fields}) for div in dividends]


@router.post("/dividends", response_model=Dividend)
async def create_dividend(dividend: DividendCreate):
    """Create a new dividend."""
    with get_db() as conn:
        div_id = insert_dividend(conn, dividend.model_dump())
        return Dividend(id=div_id, **dividend.model_dump())


@router.put("/dividends/{dividend_id}", response_model=Dividend)
async def edit_dividend(dividend_id: int, dividend: DividendCreate):
    """Update a dividend."""
    with get_db() as conn:
        if not update_dividend(conn, dividend_id, dividend.model_dump()):
            raise HTTPException(status_code=404, detail="Dividend not found")
        return Dividend(id=dividend_id, **dividend.model_dump())


@router.delete("/dividends/{dividend_id}")
async def remove_dividend(dividend_id: int):
    """Delete a dividend."""
    with get_db() as conn:
        if delete_dividend(conn, dividend_id):
            return {"message": "Dividend deleted"}
        raise HTTPException(status_code=404, detail="Dividend not found")


@router.get("/dividends/calendar", response_model=DividendCalendarResponse)
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


@router.post("/dividends/fetch-history/{ticker}")
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
                    'notes': f'Auto-imported: \u20ac{dividend_per_share:.4f}/aandeel \u00d7 {shares_on_ex_date} aandelen ({country}: {withholding_rate*100:.0f}% inhouding)'
                }
                insert_dividend(conn, dividend_data)
                added_count += 1

        return {
            "message": f"Added {added_count} dividends",
            "count": added_count,
            "total_found": len(dividend_history)
        }
