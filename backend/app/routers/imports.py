import logging
import os
from io import BytesIO
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from ..models import ImportConfirmRequest
from ..services.database import (
    get_db, get_all_transactions, get_all_dividends, get_stock_info,
    insert_transaction, insert_dividend, insert_cash_transaction, insert_stock_info,
    update_stock_yahoo_ticker,
)
from ..services.market_data import resolve_yahoo_ticker_from_isin

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/upload")
async def upload_import_file(
    file: UploadFile = File(...),
    broker: Optional[str] = Form(None),
):
    """
    Upload a broker export file for parsing.
    Returns parsed preview data without importing.
    """
    from ..services.parsers import detect_broker, get_parser
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
            except Exception as e:
                logging.getLogger(__name__).warning(f"Non-critical error resolving Yahoo ticker for ISIN {stock.isin}: {e}")

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


@router.post("/confirm")
async def confirm_import(data: ImportConfirmRequest):
    """
    Confirm and execute the import of parsed data.
    Expects: { transactions: [...], dividends: [...], cash_transactions: [...], stocks: [...] }
    """
    with get_db() as conn:
        imported = {
            "transactions": 0,
            "dividends": 0,
            "cash_transactions": 0,
            "stocks": 0,
        }
        errors = []

        # 1. Import stocks first (so transactions can reference them)
        for stock in data.stocks:
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
        for stock in data.stocks:
            if not stock.get("yahoo_ticker") and stock.get("isin"):
                stock_info_data = get_stock_info(conn, stock["ticker"])
                if stock_info_data and stock_info_data.get("manual_price_tracking"):
                    continue  # Skip manual-tracked stocks
                try:
                    yahoo_ticker = resolve_yahoo_ticker_from_isin(stock["isin"])
                    if yahoo_ticker:
                        update_stock_yahoo_ticker(conn, stock["ticker"], yahoo_ticker)
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Non-critical error enriching Yahoo ticker for {stock['ticker']}: {e}")

        # 2. Ensure broker(s) exist
        broker_names = set()
        for tx in data.transactions:
            if tx.get("broker"):
                broker_names.add(tx["broker"])
        for cash in data.cash_transactions:
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
        for tx in data.transactions:
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
        for div in data.dividends:
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
        for cash in data.cash_transactions:
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
