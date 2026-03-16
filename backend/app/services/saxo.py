"""
Saxo OpenAPI client for fetching positions and balances.

Uses OAuth2 Authorization Code flow for authentication.
Configuration (client_id, client_secret, redirect_uri, auth_url, token_url) is stored in the database.
"""
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def derive_base_url(auth_url: str) -> str:
    """Derive the Saxo OpenAPI base URL from the authorization endpoint.

    SIM auth (sim.logonvalidation.net) -> gateway.saxobank.com/sim/openapi
    LIVE auth (live.logonvalidation.net) -> gateway.saxobank.com/openapi
    """
    if "sim." in auth_url.lower():
        return "https://gateway.saxobank.com/sim/openapi"
    return "https://gateway.saxobank.com/openapi"


def get_auth_url(config: dict, state: str) -> str:
    """Build Saxo authorization URL using stored config."""
    params = {
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "state": state,
    }
    return f"{config['auth_url']}?{urlencode(params)}"


def exchange_code_for_tokens(config: dict, code: str) -> dict:
    """Exchange authorization code for access + refresh token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config["redirect_uri"],
        "client_id": config["client_id"],
    }
    if config.get("client_secret"):
        data["client_secret"] = config["client_secret"]
    resp = requests.post(config["token_url"], data=data)
    resp.raise_for_status()
    result = resp.json()
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in", 1200),
        "token_type": result.get("token_type", "Bearer"),
    }


def refresh_access_token(config: dict, refresh_token: str) -> dict:
    """Refresh an expired access token using the refresh token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "redirect_uri": config["redirect_uri"],
        "client_id": config["client_id"],
    }
    if config.get("client_secret"):
        data["client_secret"] = config["client_secret"]
    resp = requests.post(config["token_url"], data=data)
    resp.raise_for_status()
    result = resp.json()
    return {
        "access_token": result["access_token"],
        "refresh_token": result.get("refresh_token", refresh_token),
        "expires_in": result.get("expires_in", 1200),
        "token_type": result.get("token_type", "Bearer"),
    }


def get_valid_token(conn) -> Optional[str]:
    """Get a valid access token, refreshing automatically if expired."""
    from .database import get_saxo_tokens, save_saxo_tokens, get_saxo_config

    tokens = get_saxo_tokens(conn)
    if not tokens or not tokens.get("access_token"):
        return None

    access_token = tokens["access_token"]
    expiry = tokens.get("expiry")
    refresh_token = tokens.get("refresh_token")

    # Check if token is expired (with 60s buffer)
    if expiry:
        try:
            expiry_dt = datetime.fromisoformat(expiry)
            if datetime.now() >= expiry_dt - timedelta(seconds=60):
                if refresh_token:
                    logger.info("Access token expired, refreshing...")
                    config = get_saxo_config(conn)
                    new_tokens = refresh_access_token(config, refresh_token)
                    new_expiry = datetime.now() + timedelta(seconds=new_tokens["expires_in"])
                    save_saxo_tokens(
                        conn,
                        new_tokens["access_token"],
                        new_tokens["refresh_token"],
                        new_expiry.isoformat(),
                    )
                    return new_tokens["access_token"]
                else:
                    logger.warning("Access token expired and no refresh token available")
                    return None
        except (ValueError, TypeError):
            pass

    return access_token


class SaxoClient:
    def __init__(self, access_token: str, config: dict):
        self.base_url = derive_base_url(config.get("auth_url", ""))
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        })

    def test_connection(self) -> dict:
        """Test token validity by fetching account info."""
        resp = self.session.get(f"{self.base_url}/port/v1/accounts/me")
        resp.raise_for_status()
        data = resp.json()
        # The /accounts/me endpoint returns a Data array
        accounts = data.get("Data", [])
        if accounts:
            account = accounts[0]
            return {
                "account_id": account.get("AccountId"),
                "account_key": account.get("AccountKey"),
                "client_id": account.get("ClientId"),
                "client_key": account.get("ClientKey"),
                "currency": account.get("Currency"),
                "display_name": account.get("DisplayName", ""),
            }
        return {"account_id": None, "display_name": "Onbekend account"}

    def get_positions(self) -> list[dict]:
        """Fetch all open positions."""
        resp = self.session.get(
            f"{self.base_url}/port/v1/positions/me",
            params={"FieldGroups": "PositionBase,PositionView,DisplayAndFormat"},
        )
        resp.raise_for_status()
        data = resp.json()

        # Log raw response structure for first position
        raw_data = data.get("Data", [])
        if raw_data:
            first = raw_data[0]
            logger.info(f"First position keys: {list(first.keys())}")
            if "PositionView" in first:
                logger.info(f"PositionView keys: {list(first['PositionView'].keys())}")
                logger.info(f"PositionView data: {first['PositionView']}")
            if "DisplayAndFormat" in first:
                logger.info(f"DisplayAndFormat keys: {list(first['DisplayAndFormat'].keys())}")

        positions = []
        for pos in raw_data:
            base = pos.get("PositionBase", {})
            view = pos.get("PositionView", {})
            display = pos.get("DisplayAndFormat", {})

            amount = base.get("Amount", 0)
            current_price = view.get("CurrentPrice", 0)
            market_value = view.get("MarketValue", 0)
            exposure = view.get("Exposure", 0)
            market_value_open = view.get("MarketValueOpen", 0)
            pnl = view.get("ProfitLossOnTrade", 0)
            pnl_percent = view.get("ProfitLossOnTradeInPercentage", 0)

            # Outside market hours all live values can be 0.
            # Use MarketValueOpen (= cost basis) + PnL as fallback.
            # Saxo uses negative values for long positions (cost convention), so use abs().
            if market_value == 0 and market_value_open != 0:
                market_value = abs(market_value_open) + pnl
                logger.info(f"Using MarketValueOpen fallback: market_value={market_value} (|open|={abs(market_value_open)} + pnl={pnl}) for {display.get('Symbol', '?')}")

            if market_value == 0 and exposure != 0:
                market_value = abs(exposure)

            # Fallback: calculate current_price from market_value if missing
            if current_price == 0 and market_value != 0 and amount != 0:
                current_price = abs(market_value) / abs(amount)
                logger.info(f"Calculated current_price={current_price} from market_value={market_value}/amount={amount} for {display.get('Symbol', '?')}")

            # Fallback: calculate pnl_percent from pnl and cost basis
            if pnl_percent == 0 and pnl != 0 and market_value_open != 0:
                cost_basis = abs(market_value_open)
                if cost_basis != 0:
                    pnl_percent = (pnl / cost_basis) * 100
                    logger.info(f"Calculated pnl_percent={pnl_percent:.2f}% from pnl={pnl}/cost_basis={cost_basis} for {display.get('Symbol', '?')}")
            elif pnl_percent == 0 and pnl != 0 and exposure != 0:
                cost_basis = exposure - pnl
                if cost_basis != 0:
                    pnl_percent = (pnl / cost_basis) * 100

            positions.append({
                "uic": base.get("Uic"),
                "amount": amount,
                "asset_type": base.get("AssetType", ""),
                "current_price": current_price,
                "market_value": market_value,
                "pnl": pnl,
                "pnl_percent": pnl_percent,
                "description": display.get("Description", ""),
                "currency": display.get("Currency", ""),
                "symbol": display.get("Symbol", ""),
            })
        return positions

    def get_raw_positions(self) -> dict:
        """Fetch raw positions response for debugging."""
        resp = self.session.get(
            f"{self.base_url}/port/v1/positions/me",
            params={"FieldGroups": "PositionBase,PositionView,DisplayAndFormat"},
        )
        resp.raise_for_status()
        return resp.json()

    def get_raw_instrument_details(self, uics: list[int], asset_types: set[str] | None = None) -> dict:
        """Fetch raw instrument details response for debugging."""
        if not uics:
            return {}
        if not asset_types:
            asset_types = {"Stock", "Etf", "Fund", "CfdOnStock", "CfdOnEtf", "CfdOnFund"}
        uic_str = ",".join(str(u) for u in uics)
        asset_types_str = ",".join(sorted(asset_types))
        resp = self.session.get(
            f"{self.base_url}/ref/v1/instruments/details",
            params={"Uics": uic_str, "AssetTypes": asset_types_str},
        )
        resp.raise_for_status()
        return resp.json()

    def get_balances(self) -> dict:
        """Fetch account balances."""
        resp = self.session.get(f"{self.base_url}/port/v1/balances/me")
        resp.raise_for_status()
        data = resp.json()
        return {
            "total_value": data.get("TotalValue", 0),
            "cash_balance": data.get("CashBalance", 0),
            "positions_value": data.get("UnrealizedPositionsValue", 0),
            "unrealized_pnl": data.get("UnrealizedValue", 0),
            "currency": data.get("Currency", "EUR"),
            "margin_available": data.get("MarginAvailableForTrading", 0),
        }

    def get_corporate_action_events(self, event_status: str = "Past") -> tuple[list[dict], bool]:
        """Fetch corporate action events (dividends) from Saxo CA endpoint.

        Args:
            event_status: Past, Active, or Upcoming

        Returns (events, endpoint_available) tuple.
        endpoint_available is False on 403/404 (license required) or exceptions.
        """
        try:
            resp = self.session.get(
                f"{self.base_url}/ca/v2/events",
                params={"EventStatus": event_status},
            )
            if resp.status_code in (403, 404):
                logger.info(f"CA endpoint not available (HTTP {resp.status_code})")
                return [], False
            resp.raise_for_status()
            data = resp.json()

            events = []
            for event in data.get("Data", []):
                event_type = event.get("EventType", {}).get("Code", "")
                if event_type not in ("DVCA", "DVOP", "DRIP"):
                    continue

                events.append({
                    "source": "ca",
                    "event_id": event.get("EventId"),
                    "uic": event.get("Uic"),
                    "ex_date": event.get("ExDate", ""),
                    "payment_date": event.get("PaymentDate", ""),
                    "gross_dividend_per_share": event.get("GrossDividendPerShare", 0),
                    "currency": event.get("Currency", ""),
                    "total_tax": event.get("TotalTax", 0),
                    "holdings": event.get("Holdings", []),
                    "event_type": event_type,
                })
            logger.info(f"CA endpoint returned {len(events)} dividend events (status={event_status})")
            return events, True
        except Exception as e:
            logger.error(f"Error fetching CA events: {e}")
            return [], False

    def get_dividend_transactions(self, from_date: str | None = None) -> tuple[list[dict], bool]:
        """Fetch dividend transactions from historical transactions endpoint (fallback).

        Returns (events, endpoint_available) tuple.
        endpoint_available is False on 403/404 or exceptions.
        """
        try:
            params = {
                "TransactionTypes": "CorporateAction",
                "FieldGroups": "DisplayAndFormat",
            }
            if from_date:
                params["FromDate"] = from_date

            resp = self.session.get(
                f"{self.base_url}/hist/v3/transactions",
                params=params,
            )
            if resp.status_code in (403, 404):
                logger.info(f"Transaction history endpoint not available (HTTP {resp.status_code})")
                return [], False
            resp.raise_for_status()
            data = resp.json()

            dividend_subtypes = {"CashDividend", "DividendOption", "DividendReinvestment"}
            events = []
            for tx in data.get("Data", []):
                subtype = tx.get("TransactionSubType", "")
                if subtype not in dividend_subtypes:
                    continue

                events.append({
                    "source": "hist",
                    "uic": tx.get("Uic"),
                    "amount": tx.get("Amount", 0),
                    "currency": tx.get("Currency", tx.get("DisplayAndFormat", {}).get("Currency", "")),
                    "booking_date": tx.get("BookingDate", tx.get("ValueDate", "")),
                    "subtype": subtype,
                })
            logger.info(f"Transaction history returned {len(events)} dividend transactions")
            return events, True
        except Exception as e:
            logger.error(f"Error fetching dividend transactions: {e}")
            return [], False

    def get_instrument_details(self, uics: list[int], asset_types: set[str] | None = None) -> list[dict]:
        """Fetch instrument details (ISIN, description, etc.) for given UICs."""
        if not uics:
            return []
        if not asset_types:
            asset_types = {"Stock", "Etf", "Fund", "CfdOnStock", "CfdOnEtf", "CfdOnFund"}
        uic_str = ",".join(str(u) for u in uics)
        asset_types_str = ",".join(sorted(asset_types))
        logger.info(f"Fetching instrument details for {len(uics)} UICs, AssetTypes: {asset_types_str}")
        resp = self.session.get(
            f"{self.base_url}/ref/v1/instruments/details",
            params={"Uics": uic_str, "AssetTypes": asset_types_str},
        )
        resp.raise_for_status()
        data = resp.json()

        # Log raw response for first instrument
        raw_instruments = data.get("Data", [])
        if raw_instruments:
            first = raw_instruments[0]
            logger.info(f"First instrument keys: {list(first.keys())}")
            logger.info(f"First instrument Isin={first.get('Isin', 'MISSING')}, Symbol={first.get('Symbol', 'MISSING')}")

        instruments = []
        for inst in raw_instruments:
            instruments.append({
                "uic": inst.get("Uic"),
                "isin": inst.get("Isin", ""),
                "description": inst.get("Description", ""),
                "currency": inst.get("CurrencyCode", ""),
                "asset_type": inst.get("AssetType", ""),
                "symbol": inst.get("Symbol", ""),
                "exchange_id": inst.get("ExchangeId", ""),
            })
        logger.info(f"Got {len(instruments)} instrument details (requested {len(uics)} UICs)")
        return instruments


def match_positions_with_local(positions: list[dict], instruments: list[dict], local_stocks: list[dict]) -> list[dict]:
    """
    Match Saxo positions with local stock_info via ticker symbol.

    Saxo API does not return ISINs due to license restrictions, so we match
    by parsing the base ticker from the Saxo symbol (e.g. "MSFT:xnas" -> "MSFT")
    and comparing against local stocks' ticker and yahoo_ticker fields.

    Returns enriched positions with matched_ticker, isin, symbol, and exchange_id fields.
    """
    # Build UIC lookup from instruments
    uic_to_instrument = {inst["uic"]: inst for inst in instruments}

    # Build ticker lookup from local stocks (both ticker and yahoo_ticker)
    ticker_to_stock = {}
    for stock in local_stocks:
        ticker_to_stock[stock["ticker"].upper()] = stock
        if stock.get("yahoo_ticker"):
            ticker_to_stock[stock["yahoo_ticker"].upper()] = stock

    # Build Saxo symbol -> Yahoo ticker mapping for direct lookups
    from .parsers.saxo import SAXO_TO_YAHOO_TICKER
    saxo_symbol_to_yahoo = {k.upper(): v.upper() for k, v in SAXO_TO_YAHOO_TICKER.items()}

    enriched = []
    for pos in positions:
        inst = uic_to_instrument.get(pos["uic"], {})

        # Parse base ticker from Saxo symbol (e.g. "MSFT:xnas" -> "MSFT")
        symbol = pos.get("symbol", "")
        base_ticker = symbol.split(":")[0].upper() if ":" in symbol else symbol.upper()

        # Try direct mapping first (e.g. "LOCK-2673:PAR" -> "ENGI.PA")
        mapped_yahoo = saxo_symbol_to_yahoo.get(symbol.upper())
        matched_stock = None
        if mapped_yahoo:
            matched_stock = ticker_to_stock.get(mapped_yahoo)

        # Fallback: try to match by base ticker
        if not matched_stock:
            matched_stock = ticker_to_stock.get(base_ticker)
        matched_ticker = matched_stock["ticker"] if matched_stock else None
        isin = matched_stock.get("isin", "") if matched_stock else ""

        if matched_ticker:
            logger.info(f"Matched Saxo symbol '{symbol}' -> local ticker '{matched_ticker}'")
        else:
            logger.info(f"No local match for Saxo symbol '{symbol}' (base_ticker='{base_ticker}')")

        enriched.append({
            **pos,
            "isin": isin,  # From local stock, not from Saxo API
            "matched_ticker": matched_ticker,
            "instrument_symbol": inst.get("symbol", ""),
            "exchange_id": inst.get("exchange_id", ""),
        })

    return enriched


def resolve_ticker_from_saxo(symbol: str, isin: str = "") -> tuple[str, Optional[str]]:
    """
    Resolve a Yahoo Finance ticker from a Saxo symbol and/or ISIN.

    Returns (app_ticker, yahoo_ticker).
    """
    from .parsers.saxo import SAXO_TO_YAHOO_TICKER

    # 1. Try direct mapping
    yahoo_ticker = SAXO_TO_YAHOO_TICKER.get(symbol)
    if yahoo_ticker:
        return yahoo_ticker, yahoo_ticker

    # 2. Derive from symbol (e.g. "AAPL:xnas" -> "AAPL")
    if symbol and ":" in symbol:
        base = symbol.split(":")[0]
        return base, None

    # 3. Fallback to ISIN prefix as ticker
    if isin and len(isin) >= 2:
        return isin, None

    return symbol or "UNKNOWN", None


def resolve_country_from_isin(isin: str) -> str:
    """Determine country from ISIN prefix."""
    from .parsers.saxo import ISIN_COUNTRY_MAP
    if isin and len(isin) >= 2:
        return ISIN_COUNTRY_MAP.get(isin[:2], "Onbekend")
    return "Onbekend"


def process_saxo_dividends(
    ca_events: list[dict],
    enriched_positions: list[dict],
    local_stocks: list[dict],
    existing_dividends: list[dict],
    all_transactions: list[dict],
) -> tuple[list[dict], dict]:
    """Process Saxo dividend events into dividend dicts ready for insert_dividend().

    Returns (new_dividends, stats) where stats has skipped_duplicate, skipped_unmatched counts.
    """
    # Build UIC -> ticker map from matched positions
    uic_to_ticker = {}
    uic_to_isin = {}
    for pos in enriched_positions:
        if pos.get("matched_ticker") and pos.get("uic"):
            uic_to_ticker[pos["uic"]] = pos["matched_ticker"]
            uic_to_isin[pos["uic"]] = pos.get("isin", "")

    # Build dedup set from existing dividends: (ticker, ex_date_str, rounded_amount)
    dedup_set = set()
    for div in existing_dividends:
        ex_date_str = str(div["ex_date"]) if not isinstance(div["ex_date"], str) else div["ex_date"]
        dedup_set.add((div["ticker"], ex_date_str, str(round(div["bruto_amount"], 2))))

    # Group transactions by ticker for shares-on-date calculation
    tx_by_ticker = {}
    for tx in all_transactions:
        ticker = tx["ticker"]
        if ticker not in tx_by_ticker:
            tx_by_ticker[ticker] = []
        tx_by_ticker[ticker].append(tx)

    # Withholding tax rates (same as fetch-history endpoint)
    stock_lookup = {s["ticker"]: s for s in local_stocks}

    withholding_rates = {
        "Verenigde Staten": 0.15,
        "Nederland": 0.15,
        "België": 0.30,
        "Duitsland": 0.2638,
        "Frankrijk": 0.30,
    }

    new_dividends = []
    stats = {"skipped_duplicate": 0, "skipped_unmatched": 0}

    for event in ca_events:
        uic = event.get("uic")
        ticker = uic_to_ticker.get(uic)

        if not ticker:
            stats["skipped_unmatched"] += 1
            continue

        isin = uic_to_isin.get(uic, "")
        stock_info = stock_lookup.get(ticker, {})
        country = stock_info.get("country", "")
        withholding_rate = withholding_rates.get(country, 0.30)

        if event.get("source") == "ca":
            # Corporate Action event: dividend per share, need to multiply
            ex_date_str = event.get("ex_date", "")[:10]  # YYYY-MM-DD
            gross_per_share = event.get("gross_dividend_per_share", 0)
            currency = event.get("currency", "USD")

            if not ex_date_str or gross_per_share <= 0:
                continue

            # Calculate shares held on ex-date
            shares_on_ex_date = 0
            for tx in tx_by_ticker.get(ticker, []):
                tx_date_str = tx["date"] if isinstance(tx["date"], str) else tx["date"].strftime("%Y-%m-%d")
                if tx_date_str <= ex_date_str:
                    if tx["transaction_type"] == "BUY":
                        shares_on_ex_date += tx["quantity"]
                    else:
                        shares_on_ex_date -= tx["quantity"]

            if shares_on_ex_date <= 0:
                continue

            bruto_amount = round(gross_per_share * shares_on_ex_date, 2)

            # Tax: use event TotalTax if available, otherwise calculate
            total_tax = event.get("total_tax", 0)
            if total_tax and total_tax > 0:
                withheld_tax = round(total_tax, 2)
            else:
                withheld_tax = round(bruto_amount * withholding_rate, 2)

            net_amount = round(bruto_amount - withheld_tax, 2)

            # Dedup check
            dedup_key = (ticker, ex_date_str, str(round(bruto_amount, 2)))
            if dedup_key in dedup_set:
                stats["skipped_duplicate"] += 1
                continue

            dedup_set.add(dedup_key)
            new_dividends.append({
                "ticker": ticker,
                "isin": isin,
                "ex_date": ex_date_str,
                "bruto_amount": bruto_amount,
                "currency": currency,
                "withheld_tax": withheld_tax,
                "net_amount": net_amount,
                "received": True,
                "notes": f"Saxo CA sync: {gross_per_share:.4f}/aandeel x {shares_on_ex_date} ({country}: {withholding_rate*100:.0f}%)",
            })

        elif event.get("source") == "hist":
            # Historical transaction: amount is already total
            booking_date = event.get("booking_date", "")[:10]
            amount = event.get("amount", 0)
            currency = event.get("currency", "USD")

            if not booking_date or amount <= 0:
                continue

            bruto_amount = round(amount, 2)

            # Dedup check
            dedup_key = (ticker, booking_date, str(round(bruto_amount, 2)))
            if dedup_key in dedup_set:
                stats["skipped_duplicate"] += 1
                continue

            dedup_set.add(dedup_key)
            new_dividends.append({
                "ticker": ticker,
                "isin": isin,
                "ex_date": booking_date,
                "bruto_amount": bruto_amount,
                "currency": currency,
                "withheld_tax": 0,
                "net_amount": bruto_amount,
                "received": True,
                "notes": f"Saxo transactie sync (geen bronbelasting info beschikbaar)",
            })

    return new_dividends, stats
