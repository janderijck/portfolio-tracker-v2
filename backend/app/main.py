from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import pandas as pd
from io import StringIO

from .models import (
    Transaction, TransactionCreate, Dividend, DividendCreate,
    CashTransaction, CashTransactionCreate, PortfolioHolding,
    PortfolioSummary, PortfolioResponse, DividendSummary,
    CashFlowSummary, FXAnalysis, TaxCalculation, CSVUploadResponse
)
from .services.database import (
    get_db, insert_transaction, get_all_transactions, delete_transaction,
    insert_dividend, get_all_dividends, delete_dividend,
    insert_cash_transaction, get_cash_transactions,
    get_portfolio_holdings, get_cached_price, save_price_to_cache,
    get_stock_info
)
from .services.calculations import (
    get_current_price, get_current_exchange_rate,
    calculate_portfolio_performance, calculate_dividend_summary,
    calculate_cash_flow, calculate_fx_gain_loss, TaxCalculator
)

app = FastAPI(
    title="Portfolio Tracker API",
    description="API for tracking stock portfolio, dividends, and cash flow",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Portfolio Tracker API v2", "status": "running"}


# Portfolio endpoints
@app.get("/api/portfolio", response_model=PortfolioResponse)
async def get_portfolio():
    """Get all portfolio holdings with current values."""
    with get_db() as conn:
        holdings_raw = get_portfolio_holdings(conn)

        if not holdings_raw:
            return PortfolioResponse(
                holdings=[],
                summary=PortfolioSummary(
                    total_invested_eur=0,
                    total_current_value_eur=0,
                    total_gain_loss_eur=0,
                    total_gain_loss_percent=0,
                    total_dividends_eur=0,
                    has_usd_holdings=False
                )
            )

        holdings = []
        eur_invested = 0
        eur_current = 0
        eur_dividends = 0
        usd_invested = 0
        usd_current = 0
        usd_dividends = 0
        has_usd = False

        # Get exchange rates
        usd_eur_rate = get_current_exchange_rate('USD', 'EUR')

        for row in holdings_raw:
            ticker = row['ticker']
            currency = row['currency']
            quantity = row['total_quantity']

            # Get current price
            price_info = get_current_price(ticker)
            current_price = price_info['current_price'] if price_info else None

            # Calculate dividend summary
            div_summary = calculate_dividend_summary(conn, ticker)

            # Determine if USD account
            avg_exchange_rate = row.get('avg_exchange_rate', 1.0)
            is_usd_account = currency == 'USD' and avg_exchange_rate == 1.0

            # Calculate averages
            total_invested = row['total_invested'] + row['total_fees']
            total_invested_eur = row['total_invested_eur'] + row['total_fees_eur']
            avg_price = total_invested / quantity if quantity > 0 else 0
            avg_price_eur = total_invested_eur / quantity if quantity > 0 else 0

            # Calculate performance
            if current_price:
                if is_usd_account:
                    # Keep in USD
                    current_value = current_price * quantity
                    gain_loss = current_value - total_invested
                    usd_invested += total_invested
                    usd_current += current_value
                    usd_dividends += div_summary['total_netto']
                    has_usd = True
                else:
                    # Convert to EUR
                    exchange_rate = usd_eur_rate if currency == 'USD' else 1.0
                    current_price_eur = current_price * exchange_rate
                    current_value = current_price_eur * quantity
                    gain_loss = current_value - total_invested_eur
                    eur_invested += total_invested_eur
                    eur_current += current_value
                    eur_dividends += div_summary['total_netto']

                gain_loss_percent = (gain_loss / (total_invested_eur if not is_usd_account else total_invested) * 100) if total_invested > 0 else 0
            else:
                current_value = None
                gain_loss = None
                gain_loss_percent = None

            holdings.append(PortfolioHolding(
                ticker=ticker,
                isin=row['isin'],
                name=row['name'],
                broker=row['broker'],
                quantity=quantity,
                avg_purchase_price=avg_price,
                avg_purchase_price_eur=avg_price_eur,
                total_invested=total_invested,
                total_invested_eur=total_invested_eur,
                total_fees=row['total_fees'],
                total_fees_eur=row['total_fees_eur'],
                currency=currency,
                current_price=current_price,
                current_value=current_value,
                gain_loss=gain_loss,
                gain_loss_percent=gain_loss_percent,
                dividends_received=div_summary['total_netto'],
                is_usd_account=is_usd_account
            ))

        # Calculate totals
        total_gain_loss_eur = eur_current - eur_invested
        total_gain_loss_percent = (total_gain_loss_eur / eur_invested * 100) if eur_invested > 0 else 0

        summary = PortfolioSummary(
            total_invested_eur=eur_invested,
            total_current_value_eur=eur_current,
            total_gain_loss_eur=total_gain_loss_eur,
            total_gain_loss_percent=total_gain_loss_percent,
            total_dividends_eur=eur_dividends,
            total_invested_usd=usd_invested if has_usd else None,
            total_current_value_usd=usd_current if has_usd else None,
            total_gain_loss_usd=(usd_current - usd_invested) if has_usd else None,
            total_dividends_usd=usd_dividends if has_usd else None,
            has_usd_holdings=has_usd
        )

        return PortfolioResponse(holdings=holdings, summary=summary)


@app.get("/api/portfolio/summary", response_model=PortfolioSummary)
async def get_portfolio_summary():
    """Get portfolio summary totals."""
    response = await get_portfolio()
    return response.summary


# Transaction endpoints
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


@app.delete("/api/transactions/{transaction_id}")
async def remove_transaction(transaction_id: int):
    """Delete a transaction."""
    with get_db() as conn:
        if delete_transaction(conn, transaction_id):
            return {"message": "Transaction deleted"}
        raise HTTPException(status_code=404, detail="Transaction not found")


# Dividend endpoints
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


@app.delete("/api/dividends/{dividend_id}")
async def remove_dividend(dividend_id: int):
    """Delete a dividend."""
    with get_db() as conn:
        if delete_dividend(conn, dividend_id):
            return {"message": "Dividend deleted"}
        raise HTTPException(status_code=404, detail="Dividend not found")


@app.get("/api/dividends/summary/{ticker}", response_model=DividendSummary)
async def get_dividend_summary(ticker: str):
    """Get dividend summary for a ticker."""
    with get_db() as conn:
        summary = calculate_dividend_summary(conn, ticker)
        return DividendSummary(**summary)


# Stock endpoints
@app.get("/api/stocks/{ticker}")
async def get_stock_detail(ticker: str):
    """Get detailed information about a stock."""
    with get_db() as conn:
        # Get stock info
        info = get_stock_info(conn, ticker)

        # Get transactions
        transactions = get_all_transactions(conn, ticker)

        # Get dividends
        dividends = get_all_dividends(conn, ticker)

        # Get dividend summary
        div_summary = calculate_dividend_summary(conn, ticker)

        # Get current price
        price_info = get_current_price(ticker)

        return {
            "info": info,
            "transactions": transactions,
            "dividends": dividends,
            "dividend_summary": div_summary,
            "current_price": price_info
        }


# Cash flow endpoints
@app.get("/api/cash-flow", response_model=List[CashFlowSummary])
async def get_cash_flow(broker: Optional[str] = None):
    """Get cash flow summary per broker."""
    with get_db() as conn:
        return calculate_cash_flow(conn, broker)


@app.get("/api/cash-transactions", response_model=List[CashTransaction])
async def get_all_cash_transactions(broker: Optional[str] = None):
    """Get all cash transactions."""
    with get_db() as conn:
        transactions = get_cash_transactions(conn, broker)
        return [CashTransaction(**tx) for tx in transactions]


@app.post("/api/cash-transactions", response_model=CashTransaction)
async def create_cash_transaction(transaction: CashTransactionCreate):
    """Create a new cash transaction."""
    with get_db() as conn:
        tx_id = insert_cash_transaction(conn, transaction.model_dump())
        return CashTransaction(id=tx_id, **transaction.model_dump())


# FX Analysis endpoints
@app.get("/api/fx-analysis", response_model=List[FXAnalysis])
async def get_fx_analysis(broker: Optional[str] = None):
    """Get FX gain/loss analysis."""
    with get_db() as conn:
        return calculate_fx_gain_loss(conn, broker)


# Costs endpoint
@app.get("/api/costs")
async def get_costs():
    """Get cost breakdown (fees and taxes)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                broker,
                SUM(fees) as total_fees,
                SUM(COALESCE(taxes, 0)) as total_taxes,
                COUNT(*) as transaction_count
            FROM transactions
            GROUP BY broker
        """)

        results = []
        for row in cursor.fetchall():
            results.append({
                'broker': row['broker'],
                'total_fees': row['total_fees'],
                'total_taxes': row['total_taxes'],
                'total_costs': row['total_fees'] + row['total_taxes'],
                'transaction_count': row['transaction_count']
            })

        return results


# Tax calculation endpoint
@app.post("/api/tax/calculate", response_model=TaxCalculation)
async def calculate_tax(
    bruto_amount: float,
    ticker: str,
    broker: str
):
    """Calculate tax on a dividend amount."""
    with get_db() as conn:
        calculator = TaxCalculator(conn)
        result = calculator.calculate_tax(bruto_amount, ticker, broker)
        return TaxCalculation(**result)


# CSV Upload endpoint
@app.post("/api/portfolio/upload", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    broker: str = Query(..., description="Broker name (DEGIRO or IBKR)")
):
    """Upload and parse CSV file from broker."""
    try:
        content = await file.read()
        content_str = content.decode('utf-8')

        # Parse based on broker
        if broker.upper() == "DEGIRO":
            result = parse_degiro_csv(content_str)
        elif broker.upper() == "IBKR":
            result = parse_ibkr_csv(content_str)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported broker: {broker}")

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def parse_degiro_csv(content: str) -> CSVUploadResponse:
    """Parse DeGiro CSV format."""
    try:
        df = pd.read_csv(StringIO(content))

        # Filter dividend rows
        if 'Omschrijving' in df.columns:
            dividend_df = df[df['Omschrijving'].str.contains('Dividend', case=False, na=False)]
        else:
            return CSVUploadResponse(
                success=False,
                message="Invalid DeGiro CSV format",
                imported_count=0,
                errors=["Missing 'Omschrijving' column"]
            )

        imported = 0
        errors = []

        with get_db() as conn:
            for _, row in dividend_df.iterrows():
                try:
                    # Parse amount (European format)
                    amount_col = [c for c in df.columns if 'Unnamed' in c or c == 'Bedrag']
                    if amount_col:
                        amount_str = str(row[amount_col[0]])
                        amount_str = amount_str.replace('.', '').replace(',', '.')
                        amount = float(amount_str)
                    else:
                        continue

                    # Create dividend record
                    insert_dividend(conn, {
                        'ticker': row.get('Product', ''),
                        'isin': row.get('ISIN', ''),
                        'ex_date': row.get('Datum', ''),
                        'bruto_amount': abs(amount),
                        'currency': row.get('FX', 'EUR'),
                        'received': True,
                        'tax_paid': False
                    })
                    imported += 1

                except Exception as e:
                    errors.append(f"Row error: {str(e)}")

        return CSVUploadResponse(
            success=True,
            message=f"Imported {imported} dividend records from DeGiro",
            imported_count=imported,
            errors=errors
        )

    except Exception as e:
        return CSVUploadResponse(
            success=False,
            message=f"Failed to parse DeGiro CSV: {str(e)}",
            imported_count=0,
            errors=[str(e)]
        )


def parse_ibkr_csv(content: str) -> CSVUploadResponse:
    """Parse IBKR CSV format."""
    # TODO: Implement IBKR parsing
    return CSVUploadResponse(
        success=False,
        message="IBKR parsing not yet implemented",
        imported_count=0,
        errors=["IBKR format coming soon"]
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
