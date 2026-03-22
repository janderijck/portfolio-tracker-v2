"""
Bolero (KBC) PDF parser.

Parses Bolero portfolio report PDFs. These are snapshot reports containing:
- Positions per category (Aandeel, ETF) with: currency, quantity, name, purchase price, market
- Cash balance per currency
- No ISINs, no transaction dates, no fees, no dividends

This creates one BUY transaction per position using the average purchase price
and the report date as transaction date (snapshot import).

PDF text extraction quirks:
- Position data lines match: CURRENCY QUANTITY (BLOCKED) [NAME] PRICE TOTAL CURRENT_PRICE (CHANGE%) VALUE RETURN% [MARKET] RETURN_VALUE
- Long names/markets wrap across multiple lines. The name prefix and/or market prefix
  may appear on the line BEFORE the data line, and name suffix and/or market suffix
  may appear on the line AFTER.
- Known market names are used as anchors to separate name parts from market parts.
"""
import re
from io import BytesIO
from typing import Optional

from .base import (
    BaseParser,
    ParseResult,
    ParsedTransaction,
    ParsedCashTransaction,
    ParsedStock,
    _extract_text,
)

# Market name to (country, Yahoo Finance suffix) mapping
MARKET_MAP = {
    "euronext brussels": ("België", ".BR"),
    "euronext amsterdam": ("Nederland", ".AS"),
    "euronext paris": ("Frankrijk", ".PA"),
    "frankfurt (xetra)": ("Duitsland", ".DE"),
    "frankfurt": ("Duitsland", ".DE"),
    "usa": ("Verenigde Staten", ""),
    "london stock exchange": ("Verenigd Koninkrijk", ".L"),
}

# Known market keywords that appear in the PDF
MARKET_KEYWORDS = [
    "Euronext", "Frankfurt", "USA", "London Stock Exchange",
    "Brussels", "Amsterdam", "Paris", "(Xetra)",
]

# Currency codes used in position lines
CURRENCY_RE = r'(?:EUR|USD|GBP|CHF|SEK|NOK|DKK|CAD|AUD|JPY)'

# Pattern matching a data line: CURRENCY QUANTITY (BLOCKED) REST
DATA_LINE_RE = re.compile(
    rf'^({CURRENCY_RE})\s+(\d+)\s+\((\d+)\)\s+(.+)$'
)

# Pattern matching a data line that may be prefixed with a market keyword
# e.g., "Euronext EUR 19 (0) BREDERODE 111,70 ..."
DATA_LINE_WITH_MARKET_RE = re.compile(
    rf'^(\S+(?:\s+\S+)?)\s+({CURRENCY_RE})\s+(\d+)\s+\((\d+)\)\s+(.+)$'
)


def _parse_euro_number(s: str) -> Optional[float]:
    """Parse a European-formatted number: 1.768,64 -> 1768.64 or 58,95 -> 58.95."""
    s = s.strip()
    if not s:
        return None
    # Remove dots used as thousands separators, replace comma with period
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _country_from_market(market: str) -> str:
    """Get country name from market string."""
    market_lower = market.lower().strip()
    for key, (country, _) in MARKET_MAP.items():
        if key in market_lower:
            return country
    return "Onbekend"


def _extract_market_parts(text: str) -> tuple[str, str]:
    """Split a line into (non-market part, market part).

    E.g., "COLRUYT GROUP Euronext" -> ("COLRUYT GROUP", "Euronext")
    E.g., "NV Brussels" -> ("NV", "Brussels")
    E.g., "A-K (Xetra)" -> ("A-K", "(Xetra)")
    E.g., "Euronext" -> ("", "Euronext")
    """
    # Try each market keyword from longest to shortest
    for keyword in sorted(MARKET_KEYWORDS, key=len, reverse=True):
        idx = text.find(keyword)
        if idx >= 0:
            before = text[:idx].strip()
            market_part = text[idx:].strip()
            return before, market_part
    return text, ""


def _is_skip_line(line: str) -> bool:
    """Check if a line should be skipped during position parsing."""
    if not line:
        return True
    if line.startswith("Totaal"):
        return True
    if line.startswith("Totale"):
        return True
    skip_exact = {
        "Powered by KBC", "liated", "seitisoP", "ni",
    }
    if line in skip_exact:
        return True
    skip_starts = [
        "Portfolio ALL", "Totaal omgerekend",
        "Aantal", "Munt.", "(geblokkeerd)",
    ]
    for pat in skip_starts:
        if line.startswith(pat):
            return True
    # Skip lines that are just currency codes (e.g., "EUR EUR", "USD USD")
    if re.match(rf'^(?:{CURRENCY_RE})(?:\s+(?:{CURRENCY_RE}))*$', line):
        return True
    return False


def _is_numbers_only_line(line: str) -> bool:
    """Check if a line contains only numbers (e.g., totals like '9.890,24 9.580')."""
    return bool(re.match(r'^[\d.,\s%-]+$', line.strip()))


class BoleroParser(BaseParser):
    """Parser for Bolero (KBC) portfolio PDF reports."""

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def parse(self, file_content: BytesIO, filename: str) -> ParseResult:
        result = ParseResult(broker="Bolero")

        full_text = _extract_text(file_content, result)
        if not full_text:
            result.warnings.append("Kon geen tekst uit het PDF-bestand extraheren.")
            return result

        # Extract report date
        report_date = self._extract_report_date(full_text)
        if not report_date:
            result.warnings.append(
                "Kon de rapportdatum niet vinden. Gebruik vandaag als fallback."
            )
            from datetime import date
            report_date = date.today().isoformat()

        # Parse positions from Aandeel and ETF sections
        self._parse_positions(full_text, report_date, result)

        # Parse cash section
        self._parse_cash(full_text, report_date, result)

        # Add warnings about Bolero limitations
        result.warnings.append(
            "Bolero rapport bevat geen ISIN codes. "
            "Controleer de Yahoo tickers in het Effecten overzicht."
        )
        result.warnings.append(
            "De rapportdatum wordt gebruikt als transactiedatum. "
            "Pas dit eventueel aan na import."
        )

        return result

    def _extract_report_date(self, text: str) -> Optional[str]:
        """Extract report date from 'Aangemaakt DD/MM/YYYY' header."""
        match = re.search(r'Aangemaakt\s+(\d{2})/(\d{2})/(\d{4})', text)
        if match:
            day, month, year = match.group(1), match.group(2), match.group(3)
            return f"{year}-{month}-{day}"
        return None

    def _parse_positions(self, text: str, report_date: str, result: ParseResult):
        """Parse stock and ETF positions from the PDF text.

        The PDF has complex line wrapping. The approach:
        1. Find all "data lines" (matching CURRENCY QUANTITY (BLOCKED) ...)
        2. For each data line, look at surrounding lines for name/market parts
        3. Assemble the full name and market from the pieces
        """
        lines = text.split("\n")
        stripped = [l.strip() for l in lines]
        seen_stocks: dict[str, ParsedStock] = {}
        current_section: Optional[str] = None

        # First pass: find section boundaries and data line indices
        data_lines = []  # list of (line_index, currency, quantity, rest, market_prefix)

        for i, line in enumerate(stripped):
            if line == "Aandeel":
                current_section = "STOCK"
                continue
            elif line == "ETF":
                current_section = "ETF"
                continue

            if current_section is None:
                continue

            # Stop at the Cash section header (standalone "Cash" after positions)
            if line == "Cash":
                break

            # Try matching a standard data line: EUR 30 (0) ...
            m = DATA_LINE_RE.match(line)
            if m:
                data_lines.append({
                    "idx": i,
                    "currency": m.group(1),
                    "quantity": int(m.group(2)),
                    "rest": m.group(4),
                    "market_prefix": "",
                    "section": current_section,
                })
                continue

            # Try matching a data line prefixed with market keyword:
            # e.g., "Euronext EUR 19 (0) BREDERODE 111,70 ..."
            m2 = DATA_LINE_WITH_MARKET_RE.match(line)
            if m2:
                prefix = m2.group(1)
                # Verify the prefix looks like a market keyword
                _, market_part = _extract_market_parts(prefix)
                if market_part:
                    data_lines.append({
                        "idx": i,
                        "currency": m2.group(2),
                        "quantity": int(m2.group(3)),
                        "rest": m2.group(5),
                        "market_prefix": market_part,
                        "section": current_section,
                    })

        # Second pass: for each data line, resolve name and market from context
        for dl in data_lines:
            idx = dl["idx"]
            rest = dl["rest"]
            section = dl["section"]

            # Get the line before (if not a skip/data/section line)
            prev_line = stripped[idx - 1] if idx > 0 else ""
            # Get the line after
            next_line = stripped[idx + 1] if idx + 1 < len(stripped) else ""

            # Determine name prefix and market prefix from the previous line
            name_prefix = ""
            market_prefix = dl["market_prefix"]

            if prev_line and not _is_skip_line(prev_line) and not _is_numbers_only_line(prev_line):
                # Check if prev line is NOT a data line itself
                if not DATA_LINE_RE.match(prev_line) and not DATA_LINE_WITH_MARKET_RE.match(prev_line):
                    # Check if prev line is a section header
                    if prev_line not in ("Aandeel", "ETF", "Cash"):
                        name_part, mkt_part = _extract_market_parts(prev_line)
                        if name_part:
                            name_prefix = name_part
                        if mkt_part and not market_prefix:
                            market_prefix = mkt_part

            # Determine name suffix and market suffix from the next line
            name_suffix = ""
            market_suffix = ""

            if next_line and not _is_skip_line(next_line) and not _is_numbers_only_line(next_line):
                if not DATA_LINE_RE.match(next_line) and not DATA_LINE_WITH_MARKET_RE.match(next_line):
                    if next_line not in ("Aandeel", "ETF", "Cash"):
                        name_part, mkt_part = _extract_market_parts(next_line)
                        if name_part:
                            name_suffix = name_part
                        if mkt_part:
                            market_suffix = mkt_part

            # Parse the data fields from 'rest'
            parsed = self._parse_data_fields(rest)
            if not parsed:
                result.skipped_rows += 1
                result.warnings.append(f"Kon positierij niet parsen: {rest[:80]}")
                continue

            inline_name, purchase_price, inline_market = parsed

            # Assemble full name, handling hyphenated wraps
            # e.g., "VANECK UC.ETFS-SEMICON.ETF-" + "A-K" -> "VANECK UC.ETFS-SEMICON.ETF-A-K"
            name_parts = [p for p in [name_prefix, inline_name, name_suffix] if p]
            full_name = name_parts[0] if name_parts else ""
            for part in name_parts[1:]:
                if full_name.endswith("-"):
                    full_name += part
                else:
                    full_name += " " + part
            full_name = full_name.strip()

            # Assemble full market
            market_parts = [p for p in [market_prefix, inline_market, market_suffix] if p]
            full_market = " ".join(market_parts).strip()

            if not full_name:
                result.skipped_rows += 1
                result.warnings.append(f"Geen naam gevonden voor positie op regel {idx}")
                continue

            tx = ParsedTransaction(
                date=report_date,
                broker="Bolero",
                transaction_type="BUY",
                name=full_name,
                ticker=full_name,
                isin="",
                quantity=float(dl["quantity"]),
                price_per_share=purchase_price,
                currency=dl["currency"],
                fees=0.0,
                taxes=0.0,
                exchange_rate=1.0,
                fees_currency="EUR",
                notes=f"Bolero snapshot import - {section}",
                source_id=f"BOLERO-{report_date}-{full_name}-{dl['quantity']}",
            )
            result.transactions.append(tx)

            stock_key = f"{full_name}-{dl['currency']}"
            if stock_key not in seen_stocks:
                country = _country_from_market(full_market) if full_market else "Onbekend"
                seen_stocks[stock_key] = ParsedStock(
                    ticker=full_name,
                    isin="",
                    name=full_name,
                    asset_type=section,
                    currency=dl["currency"],
                    country=country,
                )

        result.stocks = list(seen_stocks.values())

    def _parse_data_fields(self, rest: str) -> Optional[tuple[str, float, str]]:
        """Parse the fields after currency and quantity on a data line.

        Input 'rest' is everything after 'EUR 30 (0) '.
        May contain: [NAME] PURCHASE_PRICE TOTAL_COST CURRENT_PRICE (CHANGE%) VALUE RETURN% [MARKET] RETURN_VALUE
        The NAME may be empty if it wrapped to previous/next lines.

        Returns (inline_name, purchase_price, inline_market) or None.
        """
        # Find the (CHANGE%) anchor: (0,08%) or (-0,96%) or (-1,57%)
        change_match = re.search(r'\((-?[\d,]+%)\)', rest)
        if not change_match:
            return None

        before_change = rest[:change_match.start()].strip()
        after_change = rest[change_match.end():].strip()

        # Before change: [NAME] PURCHASE_PRICE TOTAL_COST CURRENT_PRICE
        # Current price uses dot as decimal (59.65, 103, 4.7641)
        # Purchase price and total cost use comma as decimal (58,95 and 1.768,64)

        # Find current_price: last number using dot-notation before (change%)
        current_price_match = re.search(r'([\d.]+)\s*$', before_change)
        if not current_price_match:
            return None

        before_current_price = before_change[:current_price_match.start()].strip()

        # Find total_cost: last European-format number (contains comma)
        total_cost_match = re.search(r'([\d.]+,\d+)\s*$', before_current_price)
        if not total_cost_match:
            return None

        before_total_cost = before_current_price[:total_cost_match.start()].strip()

        # Find purchase_price: last European-format number
        purchase_price_match = re.search(r'([\d.]+,\d+)\s*$', before_total_cost)
        if not purchase_price_match:
            return None

        inline_name = before_total_cost[:purchase_price_match.start()].strip()
        purchase_price = _parse_euro_number(purchase_price_match.group(1))

        if purchase_price is None:
            return None

        # After change: CURRENT_VALUE RETURN% [MARKET] RETURN_VALUE
        # e.g., "1.789,5 1,18% Euronext Brussels 20,86"
        # e.g., "791,1 -23,65% USA -245,08"
        # e.g., "952,82 2,28% 21,23" (market on surrounding lines)

        # Extract inline market: text between return% and the trailing number
        after_match = re.match(
            r'[\d.,]+\s+'           # current_value
            r'-?[\d,]+%\s+'         # return%
            r'(.+?)\s+'            # middle part (market + possibly return value)
            r'(-?[\d.,]+)\s*$',    # trailing number
            after_change
        )
        inline_market = ""
        if after_match:
            middle = after_match.group(1).strip()
            # The middle could be "Euronext Brussels" or "USA" or just empty
            # Check if it contains any non-numeric text
            if not re.match(r'^-?[\d.,]+$', middle):
                inline_market = middle
        else:
            # Try without trailing number
            after_match2 = re.match(
                r'[\d.,]+\s+'
                r'-?[\d,]+%\s*'
                r'(.*)',
                after_change
            )
            if after_match2:
                remaining = after_match2.group(1).strip()
                # Remove trailing number
                remaining = re.sub(r'\s*-?[\d.,]+\s*$', '', remaining).strip()
                if remaining and not re.match(r'^-?[\d.,]+$', remaining):
                    inline_market = remaining

        return inline_name, purchase_price, inline_market

    def _parse_cash(self, text: str, report_date: str, result: ParseResult):
        """Parse the cash section from the PDF."""
        lines = text.split("\n")
        in_cash_section = False
        found_cash_header = False

        for line in lines:
            stripped = line.strip()

            if "Totaal in EUR:" in stripped:
                in_cash_section = True
                continue

            if in_cash_section and "Munt Totaal per munt" in stripped:
                found_cash_header = True
                continue

            if found_cash_header:
                if stripped.startswith("Totaal") or not stripped:
                    break

                cash_match = re.match(
                    r'^(EUR|USD|GBP|CHF)\s+([\d.,]+)\s+([\d.,]+)$',
                    stripped
                )
                if cash_match:
                    currency = cash_match.group(1)
                    amount = _parse_euro_number(cash_match.group(2))
                    if amount and amount > 0:
                        result.cash_transactions.append(
                            ParsedCashTransaction(
                                date=report_date,
                                broker="Bolero",
                                transaction_type="DEPOSIT",
                                amount=amount,
                                currency=currency,
                                notes=f"Bolero cash saldo op {report_date}",
                            )
                        )
