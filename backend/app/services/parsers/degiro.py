"""
DEGIRO CSV parser.

Parses the DEGIRO "Transactions" CSV export which contains stock buy/sell transactions.

CSV format:
- Delimiter: comma
- Decimal separator: European (comma inside quoted strings, e.g. "519,9000")
- Date format: DD-MM-YYYY
- Negative Aantal (quantity) = SELL, positive = BUY
- Columns 8 and 10 contain currency labels (after Koers and Lokale waarde)
- AutoFX Kosten and Transactiekosten are always in EUR
"""
import csv
import re
from datetime import datetime
from io import BytesIO, StringIO
from typing import Optional

from .base import (
    BaseParser,
    ParseResult,
    ParsedTransaction,
    ParsedStock,
    _country_from_isin,
)

# Exchange -> currency mapping (fallback if currency column is empty)
EXCHANGE_CURRENCY = {
    "EAM": "EUR",
    "EPA": "EUR",
    "EBR": "EUR",
    "XET": "EUR",
    "ETR": "EUR",
    "MIL": "EUR",
    "NDQ": "USD",
    "NSY": "USD",
    "NYA": "USD",
    "TDG": "EUR",
    "LSE": "GBP",
    "SWX": "CHF",
}


def _parse_european_decimal(value: str) -> float:
    """Parse a European-formatted decimal string like '519,9000' or '-3,00'."""
    if not value or not value.strip():
        return 0.0
    cleaned = value.strip().strip('"')
    if not cleaned:
        return 0.0
    # Replace comma with dot for decimal
    cleaned = cleaned.replace(",", ".")
    return float(cleaned)


class DegiroParser(BaseParser):
    """Parser for DEGIRO CSV transaction exports."""

    def supported_extensions(self) -> list[str]:
        return [".csv"]

    def parse(self, file_content: BytesIO, filename: str) -> ParseResult:
        result = ParseResult(broker="DEGIRO")

        # Read and decode the file content
        try:
            raw_bytes = file_content.read()
        except Exception as e:
            result.warnings.append(f"Kon het bestand niet lezen: {e}")
            return result

        # Try UTF-8 first, then latin-1
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1")

        try:
            reader = csv.reader(StringIO(text), delimiter=",")
            rows = list(reader)
        except Exception as e:
            result.warnings.append(f"Kon het bestand niet parsen als CSV: {e}")
            return result

        if len(rows) < 2:
            result.warnings.append("CSV bestand bevat geen data rijen")
            return result

        # Parse header row
        header = rows[0]
        col_map = self._build_column_map(header)

        if col_map is None:
            result.warnings.append(
                "Kon de DEGIRO CSV header niet herkennen. "
                "Verwacht kolommen: Datum, Product, ISIN, Aantal, Koers"
            )
            return result

        # Track unique stocks by ISIN
        seen_stocks: dict[str, ParsedStock] = {}

        # Parse each data row
        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or all(cell.strip() == "" for cell in row):
                continue

            try:
                tx = self._parse_row(row, col_map, row_idx)
                if tx:
                    result.transactions.append(tx)

                    # Track unique stocks
                    if tx.isin and tx.isin not in seen_stocks:
                        seen_stocks[tx.isin] = ParsedStock(
                            ticker=tx.ticker,
                            isin=tx.isin,
                            name=tx.name,
                            asset_type="STOCK",
                            currency=tx.currency,
                            country=_country_from_isin(tx.isin),
                        )
            except Exception as e:
                result.warnings.append(f"Rij {row_idx}: {str(e)}")
                result.skipped_rows += 1

        result.stocks = list(seen_stocks.values())
        return result

    def _build_column_map(self, header: list[str]) -> Optional[dict[str, int]]:
        """Map expected column names to their indices."""
        # Clean header values
        clean = [h.strip().lower() for h in header]

        required = {
            "datum": None,
            "product": None,
            "isin": None,
            "aantal": None,
            "koers": None,
        }

        for i, col in enumerate(clean):
            if col == "datum":
                required["datum"] = i
            elif col == "product":
                required["product"] = i
            elif col == "isin":
                required["isin"] = i
            elif col == "beurs":
                required["beurs"] = i
            elif col == "aantal":
                required["aantal"] = i
            elif col == "koers":
                required["koers"] = i
            elif col == "wisselkoers":
                required["wisselkoers"] = i
            elif col.startswith("autofx"):
                required["autofx"] = i
            elif col.startswith("transactiekosten"):
                required["transactiekosten"] = i
            elif col == "order id":
                required["order_id"] = i

        # Check that minimum required columns exist
        if any(required.get(k) is None for k in ["datum", "product", "isin", "aantal", "koers"]):
            return None

        # The currency column is right after "Koers" (an empty-header column)
        koers_idx = required["koers"]
        if koers_idx + 1 < len(header):
            required["currency"] = koers_idx + 1

        return required

    def _parse_row(
        self, row: list[str], col_map: dict[str, int], row_num: int
    ) -> Optional[ParsedTransaction]:
        """Parse a single CSV row into a ParsedTransaction."""

        def _get(key: str, default: str = "") -> str:
            idx = col_map.get(key)
            if idx is not None and idx < len(row):
                return row[idx].strip().strip('"')
            return default

        # Parse date (DD-MM-YYYY -> YYYY-MM-DD)
        date_str = _get("datum")
        if not date_str:
            return None

        try:
            parsed_date = datetime.strptime(date_str, "%d-%m-%Y")
            iso_date = parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Ongeldig datumformaat: {date_str}")

        # Product name and ISIN
        name = _get("product")
        isin = _get("isin")
        if not name or not isin:
            return None

        # Parse quantity - negative = SELL, positive = BUY
        aantal_str = _get("aantal")
        if not aantal_str:
            return None

        aantal = _parse_european_decimal(aantal_str)
        if aantal == 0:
            return None

        transaction_type = "SELL" if aantal < 0 else "BUY"
        quantity = abs(aantal)

        # Parse price (Koers)
        koers_str = _get("koers")
        price = _parse_european_decimal(koers_str)

        # Currency from the column after Koers
        currency = _get("currency", "EUR")
        if not currency:
            # Fallback: try exchange mapping
            exchange = _get("beurs", "")
            currency = EXCHANGE_CURRENCY.get(exchange, "EUR")

        # Exchange rate (Wisselkoers)
        wisselkoers_str = _get("wisselkoers", "")
        if wisselkoers_str:
            exchange_rate = _parse_european_decimal(wisselkoers_str)
            if exchange_rate == 0:
                exchange_rate = 1.0
        else:
            exchange_rate = 1.0

        # Fees: abs(Transactiekosten) + abs(AutoFX Kosten)
        transactiekosten_str = _get("transactiekosten", "0")
        autofx_str = _get("autofx", "0")
        transactiekosten = abs(_parse_european_decimal(transactiekosten_str))
        autofx = abs(_parse_european_decimal(autofx_str))
        fees = transactiekosten + autofx

        # Order ID as source_id
        order_id = _get("order_id", "")

        # Use ISIN as ticker (will be resolved later during import)
        ticker = isin

        return ParsedTransaction(
            date=iso_date,
            broker="DEGIRO",
            transaction_type=transaction_type,
            name=name,
            ticker=ticker,
            isin=isin,
            quantity=quantity,
            price_per_share=price,
            currency=currency,
            fees=round(fees, 2),
            taxes=0.0,
            exchange_rate=exchange_rate,
            fees_currency="EUR",
            notes=f"Order: {order_id}" if order_id else None,
            source_id=order_id if order_id else None,
        )
