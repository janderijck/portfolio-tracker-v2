"""
IBKR Flex Query client for fetching trades, dividends, and cash transactions.

Uses ibflex library to download and parse Flex XML statements.
Configuration (flex_token, query_id) is stored in the database.
"""
import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Optional

from ibflex import client as ibflex_client
from ibflex import parser as ibflex_parser
from ibflex import Types as ibflex_types
from ibflex.enums import BuySell, CashAction

# Monkey-patch ibflex parser to skip unknown XML attributes instead of crashing.
# IBKR regularly adds new fields (e.g. subCategory) that ibflex doesn't know about.
_original_parse_data_element = ibflex_parser.parse_data_element


def _patched_parse_data_element(elem):
    Class = getattr(ibflex_types, elem.tag)
    known_fields = {f.name for f in Class.__dataclass_fields__.values()}
    for key in list(elem.attrib):
        if key not in known_fields:
            del elem.attrib[key]
    return _original_parse_data_element(elem)


ibflex_parser.parse_data_element = _patched_parse_data_element

logger = logging.getLogger(__name__)


class IBKRClient:
    def __init__(self, token: str, query_id: str):
        self.token = token
        self.query_id = query_id

    def test_connection(self) -> dict:
        """Fetch report and return basic account info."""
        statement = self.fetch_report()
        return {
            "account_id": statement.accountId,
            "from_date": str(statement.fromDate) if statement.fromDate else None,
            "to_date": str(statement.toDate) if statement.toDate else None,
            "trades": len(statement.Trades) if statement.Trades else 0,
            "cash_transactions": len(statement.CashTransactions) if statement.CashTransactions else 0,
            "open_positions": len(statement.OpenPositions) if statement.OpenPositions else 0,
        }

    def fetch_report(self):
        """Download and parse Flex Query report. Returns FlexStatement."""
        xml_bytes = ibflex_client.download(self.token, self.query_id)
        response = ibflex_parser.parse(xml_bytes)
        if not response.FlexStatements:
            raise ValueError("Geen Flex Statements gevonden in het rapport")
        return response.FlexStatements[0]

    def parse_trades(self, statement) -> list[dict]:
        """Parse ibflex Trades into app transaction dicts."""
        if not statement.Trades:
            return []

        results = []
        for trade in statement.Trades:
            # Skip cancelled trades
            if trade.buySell in (BuySell.CANCELBUY, BuySell.CANCELSELL):
                continue

            # Skip if no essential fields
            if not trade.tradeDate or trade.quantity is None or trade.tradePrice is None:
                continue

            tx_type = "BUY" if trade.buySell == BuySell.BUY else "SELL"
            source_id = f"IBKR-T-{trade.transactionID}" if trade.transactionID else None

            results.append({
                "date": trade.tradeDate.isoformat(),
                "broker": "IBKR",
                "transaction_type": tx_type,
                "name": trade.description or trade.symbol or "",
                "ticker": trade.symbol or "",
                "isin": trade.isin or "",
                "quantity": abs(float(trade.quantity)),
                "price_per_share": float(trade.tradePrice),
                "currency": trade.currency or "USD",
                "fees": abs(float(trade.ibCommission)) if trade.ibCommission else 0.0,
                "taxes": abs(float(trade.taxes)) if trade.taxes else 0.0,
                "exchange_rate": float(trade.fxRateToBase) if trade.fxRateToBase else 1.0,
                "fees_currency": trade.currency or "USD",
                "notes": f"IBKR import (ID: {trade.transactionID})" if trade.transactionID else "IBKR import",
                "source_id": source_id,
            })

        return results

    def parse_dividends(self, statement, isin_lookup: dict) -> list[dict]:
        """Parse ibflex CashTransactions (DIVIDEND + WHTAX) into dividend dicts.

        Groups DIVIDEND and WHTAX entries by (symbol, reportDate) to pair them.
        """
        if not statement.CashTransactions:
            return []

        # Group by (symbol, reportDate)
        groups: dict[tuple, dict] = defaultdict(lambda: {
            "dividends": [],
            "whtax": [],
        })

        for ct in statement.CashTransactions:
            if ct.type == CashAction.DIVIDEND or ct.type == CashAction.PAYMENTINLIEU:
                key = (ct.symbol, str(ct.reportDate) if ct.reportDate else "")
                groups[key]["dividends"].append(ct)
            elif ct.type == CashAction.WHTAX:
                key = (ct.symbol, str(ct.reportDate) if ct.reportDate else "")
                groups[key]["whtax"].append(ct)

        results = []
        for (symbol, report_date), group in groups.items():
            if not group["dividends"]:
                continue

            # Sum all dividend entries for this group
            bruto = sum(abs(float(d.amount)) for d in group["dividends"] if d.amount)
            whtax = sum(abs(float(w.amount)) for w in group["whtax"] if w.amount)
            net = bruto - whtax

            first_div = group["dividends"][0]
            isin = first_div.isin or isin_lookup.get(symbol, "")

            # Build source_id from first dividend transaction ID
            source_id = f"IBKR-D-{first_div.transactionID}" if first_div.transactionID else None

            results.append({
                "ticker": symbol or "",
                "isin": isin,
                "ex_date": report_date,
                "bruto_amount": round(bruto, 2),
                "currency": first_div.currency or "USD",
                "withheld_tax": round(whtax, 2),
                "net_amount": round(net, 2),
                "received": True,
                "notes": "IBKR import",
                "source_id": source_id,
            })

        return results

    def parse_cash_transactions(self, statement) -> list[dict]:
        """Parse ibflex CashTransactions (Deposits & Withdrawals only)."""
        if not statement.CashTransactions:
            return []

        results = []
        for ct in statement.CashTransactions:
            if ct.type != CashAction.DEPOSITWITHDRAW:
                continue
            if ct.amount is None:
                continue

            amount = float(ct.amount)
            tx_type = "DEPOSIT" if amount > 0 else "WITHDRAWAL"
            source_id = f"IBKR-C-{ct.transactionID}" if ct.transactionID else None

            results.append({
                "date": ct.reportDate.isoformat() if ct.reportDate else datetime.now().date().isoformat(),
                "broker": "IBKR",
                "transaction_type": tx_type,
                "amount": abs(amount),
                "currency": ct.currency or "EUR",
                "source_amount": None,
                "source_currency": None,
                "exchange_rate": float(ct.fxRateToBase) if ct.fxRateToBase else None,
                "notes": "IBKR import",
                "source_id": source_id,
            })

        return results

    def get_positions(self, statement) -> tuple[list[dict], dict]:
        """Extract open positions and build symbol→ISIN lookup.

        Returns:
            (positions_list, isin_lookup_dict)
        """
        isin_lookup: dict[str, str] = {}
        positions = []

        if statement.OpenPositions:
            for pos in statement.OpenPositions:
                if pos.symbol and pos.isin:
                    isin_lookup[pos.symbol] = pos.isin

                if pos.position and float(pos.position) != 0:
                    positions.append({
                        "symbol": pos.symbol or "",
                        "isin": pos.isin or "",
                        "description": pos.description or pos.symbol or "",
                        "quantity": abs(float(pos.position)),
                        "mark_price": float(pos.markPrice) if pos.markPrice else None,
                        "cost_basis_price": float(pos.costBasisPrice) if pos.costBasisPrice else None,
                        "cost_basis_money": float(pos.costBasisMoney) if pos.costBasisMoney else None,
                        "position_value": float(pos.positionValue) if pos.positionValue else None,
                        "currency": pos.currency or "USD",
                    })

        # Also extract ISINs from trades
        if statement.Trades:
            for trade in statement.Trades:
                if trade.symbol and trade.isin and trade.symbol not in isin_lookup:
                    isin_lookup[trade.symbol] = trade.isin

        return positions, isin_lookup


def resolve_ibkr_ticker(symbol: str, isin: str) -> str:
    """Resolve IBKR symbol to an app-friendly ticker.

    US stocks keep their symbol as-is.
    EU stocks use the ISIN as key since IBKR symbols differ from Yahoo.
    """
    if not symbol:
        return isin or ""

    # US ISINs start with US
    if isin and isin.startswith("US"):
        return symbol

    # For non-US, use the symbol as-is (will be resolved via ISIN later)
    return symbol


def build_stocks_from_positions(positions: list[dict], isin_lookup: dict) -> list[dict]:
    """Build stock_info entries from IBKR positions."""
    stocks = []
    for pos in positions:
        symbol = pos["symbol"]
        isin = pos.get("isin") or isin_lookup.get(symbol, "")
        ticker = resolve_ibkr_ticker(symbol, isin)

        stocks.append({
            "ticker": ticker,
            "isin": isin,
            "name": pos.get("description", symbol),
            "asset_type": "STOCK",
            "country": _country_from_isin(isin),
            "yahoo_ticker": None,  # Will be resolved via ISIN enrichment
            "manual_price_tracking": False,
            "pays_dividend": False,
        })

    return stocks


def _country_from_isin(isin: str) -> str:
    """Derive country from ISIN prefix."""
    if not isin or len(isin) < 2:
        return "Onbekend"

    prefix = isin[:2].upper()
    country_map = {
        "US": "Verenigde Staten",
        "IE": "Ierland",
        "NL": "Nederland",
        "DE": "Duitsland",
        "FR": "Frankrijk",
        "BE": "België",
        "GB": "Verenigd Koninkrijk",
        "LU": "Luxemburg",
        "CH": "Zwitserland",
        "IT": "Italië",
        "ES": "Spanje",
        "CA": "Canada",
        "JP": "Japan",
        "AU": "Australië",
    }
    return country_map.get(prefix, "Onbekend")
