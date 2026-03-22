import logging
from fastapi import APIRouter, HTTPException
from ..models import IBKRConfig, IBKRSyncResult, IBKRStatus
from ..services.database import (
    get_db, get_ibkr_config, save_ibkr_config, clear_ibkr_config, update_ibkr_last_sync,
    get_all_stocks, get_stock_info, insert_stock_info, get_all_transactions,
    insert_transaction, insert_dividend, insert_cash_transaction,
    check_source_id_exists, update_stock_yahoo_ticker,
)
from ..services.market_data import resolve_yahoo_ticker_from_isin

router = APIRouter(prefix="/api/ibkr", tags=["ibkr"])


@router.get("/config")
async def get_ibkr_config_endpoint():
    """Get IBKR Flex Query configuration."""
    with get_db() as conn:
        config = get_ibkr_config(conn)
        return IBKRConfig(
            flex_token=config.get("flex_token", ""),
            query_id=config.get("query_id", ""),
        )


@router.put("/config")
async def save_ibkr_config_endpoint(config: IBKRConfig):
    """Save IBKR Flex Query configuration."""
    with get_db() as conn:
        save_ibkr_config(conn, config.flex_token, config.query_id)
        return config


@router.post("/test")
async def test_ibkr_connection():
    """Test IBKR connection by fetching a report."""
    from ..services.ibkr import IBKRClient

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


@router.post("/sync", response_model=IBKRSyncResult)
async def sync_ibkr():
    """Full IBKR sync: fetch report, parse trades/dividends/cash, import with dedup."""
    from ..services.ibkr import IBKRClient, build_stocks_from_positions, resolve_ibkr_ticker
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
                        except Exception as e:
                            logging.getLogger(__name__).warning(f"Non-critical error resolving Yahoo ticker for {stock['ticker']}: {e}")

            # 5. Build ticker resolution map (IBKR symbol -> app ticker)
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


@router.post("/disconnect")
async def ibkr_disconnect():
    """Clear IBKR configuration."""
    with get_db() as conn:
        clear_ibkr_config(conn)
    return {"success": True, "message": "IBKR ontkoppeld"}


@router.get("/status", response_model=IBKRStatus)
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
