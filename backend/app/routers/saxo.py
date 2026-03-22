import logging
from fastapi import APIRouter, HTTPException
from ..models import (
    SaxoConfig, SaxoPosition, SaxoBalance, SaxoSyncResult, SaxoDividendSyncResult,
    SaxoImportRequest, SaxoImportResult,
)
from ..services.database import (
    get_db, get_all_stocks, get_all_transactions, get_all_dividends, get_stock_info,
    get_saxo_config, save_saxo_config, get_saxo_tokens, save_saxo_tokens, clear_saxo_tokens,
    save_saxo_price_cache, get_all_saxo_price_cache,
    insert_stock_info, insert_dividend, insert_transaction, insert_manual_price,
    get_latest_manual_price,
)
from ..services.market_data import resolve_yahoo_ticker_from_isin

router = APIRouter(prefix="/api/saxo", tags=["saxo"])


@router.get("/config", response_model=SaxoConfig)
async def get_saxo_config_endpoint():
    """Get Saxo API configuration."""
    with get_db() as conn:
        config = get_saxo_config(conn)
        return SaxoConfig(**config) if config else SaxoConfig()


@router.put("/config", response_model=SaxoConfig)
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


@router.get("/auth-url")
async def get_saxo_auth_url():
    """Return authorization URL for Saxo OAuth flow."""
    import secrets
    from ..services.saxo import get_auth_url

    with get_db() as conn:
        config = get_saxo_config(conn)
    if not config.get("client_id"):
        raise HTTPException(status_code=400, detail="Saxo configuratie ontbreekt. Stel eerst Client ID, Secret en Redirect URI in.")

    state = secrets.token_urlsafe(32)
    url = get_auth_url(config, state)
    return {"url": url, "state": state}


@router.post("/callback")
async def saxo_oauth_callback(body: dict):
    """Exchange authorization code for tokens."""
    from ..services.saxo import exchange_code_for_tokens, SaxoClient
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


@router.post("/disconnect")
async def saxo_disconnect():
    """Clear all Saxo tokens."""
    with get_db() as conn:
        clear_saxo_tokens(conn)
    return {"success": True, "message": "Saxo ontkoppeld"}


@router.post("/test")
async def test_saxo_connection():
    """Test Saxo connection using stored OAuth token."""
    from ..services.saxo import SaxoClient, get_valid_token

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


@router.get("/positions")
async def get_saxo_positions():
    """Fetch Saxo positions and match with local stocks."""
    from ..services.saxo import SaxoClient, match_positions_with_local, get_valid_token

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


@router.get("/balances")
async def get_saxo_balances():
    """Fetch Saxo account balances."""
    from ..services.saxo import SaxoClient, get_valid_token

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


@router.post("/sync", response_model=SaxoSyncResult)
async def sync_saxo():
    """Full sync: fetch positions, match with local DB, cache Saxo prices, sync dividends."""
    from ..services.saxo import SaxoClient, match_positions_with_local, get_valid_token, process_saxo_dividends

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


@router.post("/import-positions", response_model=SaxoImportResult)
async def import_saxo_positions(request: SaxoImportRequest):
    """Import unmatched Saxo positions as local stocks with initial BUY transactions."""
    from ..services.saxo import resolve_ticker_from_saxo, resolve_country_from_isin
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


@router.get("/status")
async def get_saxo_status():
    """Get Saxo connection status and last sync time."""
    with get_db() as conn:
        tokens = get_saxo_tokens(conn)
        has_token = bool(tokens.get("access_token"))
        saxo_cache = get_all_saxo_price_cache(conn)

        # Find the most recent cache update
        last_sync = None
        if saxo_cache:
            last_sync = max(
                (v.get("updated_at") for v in saxo_cache.values() if v.get("updated_at")),
                default=None,
            )

        return {
            "connected": has_token,
            "has_token": has_token,
            "cached_prices": len(saxo_cache),
            "last_sync": last_sync,
        }


