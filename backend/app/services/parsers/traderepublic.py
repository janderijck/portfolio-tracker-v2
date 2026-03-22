"""
Trade Republic PDF parser.

Parses Trade Republic "Rekeningoverzicht" (account statement) PDF exports.
Extracts buy/sell trades, dividends, interest payments, and deposits/withdrawals.

PDF structure per transaction line:
  DATE | TYPE | DESCRIPTION | MONEY IN | MONEY OUT | BALANCE

Types: Trade, Transfer, Interest, Earnings

The PDF has two layout formats depending on description length:

Format A (short descriptions, fits on one line):
  DD Mon           <- date alone on a line
  Type Description €amount €balance
  YYYY             <- year alone on a line

Format B (long descriptions, wraps across lines):
  DD Mon description-part-1...
  Type €amount €balance
  YYYY description-part-2, quantity: X
"""
import re
from io import BytesIO
from typing import Optional

from .base import (
    BaseParser,
    ParseResult,
    ParsedTransaction,
    ParsedDividend,
    ParsedCashTransaction,
    ParsedStock,
    _country_from_isin,
    _extract_text,
)

MONTH_MAP = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

# Lines to skip (headers, footers)
SKIP_PATTERNS = [
    "TRADE REPUBLIC BANK GMBH",
    "DATE TYPE DESCRIPTION",
    "ACCOUNT STATEMENT SUMMARY",
    "ACCOUNT TRANSACTIONS",
    "PRODUCT OPENING BALANCE",
    "Securities Account",
    "Trade Republic Bank GmbH",
    "Brunnenstraße",
    "10119 Berlin",
    "Generated on",
    "BALANCE OVERVIEW",
    "ESCROW ACCOUNTS",
    "NOTES ON THE ACCOUNT STATEMENT",
    "Please check your account",
    "does not take into account",
    "corresponds to the account",
    "if you do not raise",
    "chats are subject to",
    "balances held with",
    "qualified money market",
    "on the protection",
    "Citibank",
    "AG Charlottenburg",
    "VAT-ID",
]

# Date pattern at start of line
DATE_RE = re.compile(r'^(\d{1,2}\s+\w{3})')
DATE_ONLY_RE = re.compile(r'^(\d{1,2}\s+\w{3})$')
YEAR_RE = re.compile(r'^(\d{4})\b')
TYPE_KEYWORDS = ("Trade", "Transfer", "Interest", "Earnings")


def _parse_date(day_month: str, year: str) -> Optional[str]:
    match = re.match(r'(\d{1,2})\s+(\w{3})', day_month.strip())
    if not match:
        return None
    day = match.group(1).zfill(2)
    month = MONTH_MAP.get(match.group(2))
    if not month:
        return None
    return f"{year.strip()}-{month}-{day}"


def _should_skip(line: str) -> bool:
    return any(pat in line for pat in SKIP_PATTERNS)


class TradeRepublicParser(BaseParser):
    """Parser for Trade Republic PDF account statements."""

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def parse(self, file_content: BytesIO, filename: str) -> ParseResult:
        result = ParseResult(broker="Trade Republic")
        seen_stocks: dict[str, ParsedStock] = {}

        full_text = _extract_text(file_content, result)
        if not full_text:
            result.warnings.append("Kon geen tekst uit het PDF-bestand extraheren.")
            return result

        transactions_raw = self._split_transactions(full_text)

        for tx_raw in transactions_raw:
            self._process_transaction(tx_raw, seen_stocks, result)

        # Merge fractional trades (same stock, same date, same type)
        result.transactions = self._merge_fractional_trades(result.transactions)

        result.stocks = list(seen_stocks.values())
        return result

    def _split_transactions(self, text: str) -> list[dict]:
        """Split full text into individual transaction blocks.

        Handles two formats:
        - Format A: date on own line, content on next line, year on own line
        - Format B: date + desc_part1 on one line, type + amounts on next, year + desc_part2 on next
        """
        transactions = []
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if _should_skip(line) or not line:
                i += 1
                continue

            # Format A: line is exactly "DD Mon" (date only)
            date_only = DATE_ONLY_RE.match(line)
            if date_only:
                day_month = date_only.group(1)
                i += 1
                content_lines = []
                year = None

                while i < len(lines):
                    next_line = lines[i].strip()
                    year_match = re.match(r'^(\d{4})$', next_line)
                    if year_match:
                        year = year_match.group(1)
                        i += 1
                        break
                    if _should_skip(next_line):
                        i += 1
                        continue
                    content_lines.append(next_line)
                    i += 1

                if year and content_lines:
                    content = " ".join(content_lines)
                    transactions.append({
                        "day_month": day_month,
                        "year": year,
                        "content": content,
                    })
                continue

            # Format B: line starts with "DD Mon " followed by description text
            date_inline = DATE_RE.match(line)
            if date_inline:
                day_month = date_inline.group(1)
                desc_part1 = line[date_inline.end():].strip()

                # Verify this is a valid month
                month_part = day_month.split()[-1] if day_month else ""
                if month_part not in MONTH_MAP:
                    i += 1
                    continue

                # Next line should be Type + amounts (e.g., "Trade €461.92 €4,538.08")
                i += 1
                if i >= len(lines):
                    break
                type_line = lines[i].strip()

                # Next line should start with year (e.g., "2025 EUR (C), quantity: 4")
                i += 1
                if i >= len(lines):
                    break
                year_line = lines[i].strip()
                year_match = YEAR_RE.match(year_line)

                if year_match:
                    year = year_match.group(1)
                    desc_part2 = year_line[year_match.end():].strip()

                    # Combine: desc_part1 + type_line + desc_part2
                    # type_line contains the Type keyword + amounts
                    content = f"{type_line}"
                    # The full description is desc_part1 + desc_part2
                    # But we need to pass the type + description together
                    # type_line = "Trade €461.92 €4,538.08"
                    # desc_part1 = "Buy trade LU1681... Amundi S&P 500 UCITS ETF -"
                    # desc_part2 = "EUR (C), quantity: 4"
                    # Full content needs to be: "Trade Buy trade LU1681... Amundi S&P 500 UCITS ETF - EUR (C), quantity: 4 €461.92 €4,538.08"

                    # Extract amounts from type_line
                    amounts_in_type = re.findall(r'€[\d,]+\.\d{2}', type_line)
                    # Extract the type keyword from type_line (before first €)
                    type_keyword = re.sub(r'€[\d,]+\.\d{2}', '', type_line).strip()

                    # Build combined content: Type + desc_part1 + desc_part2 + amounts
                    full_desc = f"{desc_part1} {desc_part2}".strip()
                    content = f"{type_keyword} {full_desc} {' '.join(amounts_in_type)}".strip()

                    transactions.append({
                        "day_month": day_month,
                        "year": year,
                        "content": content,
                    })
                    i += 1
                    continue
                else:
                    # Year not found where expected - might not be a transaction
                    # Back up and skip this line
                    i -= 1  # back to the line after date line
                    i += 1
                    continue

            i += 1

        return transactions

    def _process_transaction(self, tx_raw: dict, seen_stocks: dict, result: ParseResult):
        date_str = _parse_date(tx_raw["day_month"], tx_raw["year"])
        if not date_str:
            result.skipped_rows += 1
            return

        content = tx_raw["content"]

        # Extract amounts (€ values)
        amounts = re.findall(r'€([\d,]+\.\d{2})', content)
        amounts_float = [float(a.replace(",", "")) for a in amounts]

        # Remove amounts to get clean description
        desc_clean = re.sub(r'€[\d,]+\.\d{2}', '', content).strip()
        # Collapse multiple spaces
        desc_clean = re.sub(r'\s+', ' ', desc_clean)

        # Determine type from the beginning of content
        # PDF concatenates Type and Description: "TransferDeposit accepted..." or "EarningsCash Dividend..."
        if desc_clean.startswith("Trade"):
            desc_after = desc_clean[5:].strip()
            self._handle_trade(date_str, desc_after, amounts_float, seen_stocks, result)
        elif desc_clean.startswith("Interest"):
            desc_after = desc_clean[8:].strip()
            self._handle_interest(date_str, desc_after, amounts_float, result)
        elif desc_clean.startswith("Earnings"):
            desc_after = desc_clean[8:].strip()
            self._handle_earnings(date_str, desc_after, amounts_float, seen_stocks, result)
        elif desc_clean.startswith("Transfer"):
            desc_after = desc_clean[8:].strip()
            self._handle_transfer(date_str, desc_after, amounts_float, result)
        else:
            result.skipped_rows += 1

    def _handle_trade(self, date_str: str, description: str,
                      amounts: list[float], seen_stocks: dict, result: ParseResult):
        if description.startswith("Buy trade") or description.startswith("Savings plan execution"):
            tx_type = "BUY"
            if description.startswith("Buy trade"):
                desc_rest = description[len("Buy trade"):].strip()
            else:
                desc_rest = description[len("Savings plan execution"):].strip()
        elif description.startswith("Sell trade"):
            tx_type = "SELL"
            desc_rest = description[len("Sell trade"):].strip()
        else:
            result.warnings.append(f"Onbekend trade type: {description[:80]}")
            result.skipped_rows += 1
            return

        # Extract ISIN (12 chars starting with 2 letters)
        isin_match = re.search(r'([A-Z]{2}[A-Z0-9]{10})', desc_rest)
        if not isin_match:
            result.warnings.append(f"Geen ISIN gevonden in: {description[:80]}")
            result.skipped_rows += 1
            return
        isin = isin_match.group(1)

        # Extract quantity
        qty_match = re.search(r'quantity:\s*([\d.]+)', desc_rest)
        if not qty_match:
            result.warnings.append(f"Geen quantity gevonden in: {description[:80]}")
            result.skipped_rows += 1
            return
        quantity = float(qty_match.group(1))

        # Extract name: everything between ISIN and ", quantity:"
        name_match = re.search(
            r'[A-Z]{2}[A-Z0-9]{10}\s+(.*?),?\s*quantity:',
            desc_rest
        )
        name = name_match.group(1).strip().rstrip(",").strip() if name_match else "Onbekend"
        # Clean up trailing punctuation from name
        name = re.sub(r'\s*-\s*$', '', name).strip()

        if not amounts:
            result.warnings.append(f"Geen bedrag gevonden voor trade: {description[:80]}")
            result.skipped_rows += 1
            return

        amount = amounts[0]
        price_per_share = round(amount / quantity, 6) if quantity > 0 else 0

        tx = ParsedTransaction(
            date=date_str,
            broker="Trade Republic",
            transaction_type=tx_type,
            name=name,
            ticker=isin,
            isin=isin,
            quantity=quantity,
            price_per_share=price_per_share,
            currency="EUR",
            fees=0.0,
            taxes=0.0,
            exchange_rate=1.0,
            fees_currency="EUR",
            source_id=f"TR-{date_str}-{isin}-{tx_type}-{quantity}",
        )
        result.transactions.append(tx)

        # Track stock info
        if isin not in seen_stocks:
            seen_stocks[isin] = ParsedStock(
                ticker=isin,
                isin=isin,
                name=name,
                asset_type="STOCK",
                currency="EUR",
                country=_country_from_isin(isin),
            )

    def _handle_interest(self, date_str: str, description: str,
                         amounts: list[float], result: ParseResult):
        if not amounts:
            result.skipped_rows += 1
            return

        cash = ParsedCashTransaction(
            date=date_str,
            broker="Trade Republic",
            transaction_type="INTEREST",
            amount=round(amounts[0], 2),
            currency="EUR",
            notes=description.strip() if description.strip() else "Interest payment",
        )
        result.cash_transactions.append(cash)

    def _handle_earnings(self, date_str: str, description: str,
                         amounts: list[float], seen_stocks: dict, result: ParseResult):
        isin_match = re.search(r'ISIN\s+([A-Z]{2}[A-Z0-9]{10})', description)
        if not isin_match:
            result.warnings.append(f"Geen ISIN in dividend: {description[:80]}")
            result.skipped_rows += 1
            return
        isin = isin_match.group(1)

        if not amounts:
            result.skipped_rows += 1
            return

        # Trade Republic pays net dividends (after withholding tax deducted at source)
        div = ParsedDividend(
            ticker=isin,
            isin=isin,
            ex_date=date_str,
            bruto_amount=round(amounts[0], 2),
            currency="EUR",
            withheld_tax=0.0,
            net_amount=round(amounts[0], 2),
            received=True,
            notes="Cash Dividend via Trade Republic",
        )
        result.dividends.append(div)

    def _handle_transfer(self, date_str: str, description: str,
                         amounts: list[float], result: ParseResult):
        if not amounts:
            result.skipped_rows += 1
            return

        amount = amounts[0]

        if "Deposit accepted" in description or "deposit accepted" in description:
            tx_type = "DEPOSIT"
        elif "PayOut" in description or "payout" in description.lower():
            tx_type = "WITHDRAWAL"
        else:
            result.warnings.append(f"Onbekend transfer type: {description[:80]}")
            result.skipped_rows += 1
            return

        cash = ParsedCashTransaction(
            date=date_str,
            broker="Trade Republic",
            transaction_type=tx_type,
            amount=round(amount, 2) if tx_type == "DEPOSIT" else round(-amount, 2),
            currency="EUR",
            notes=description.strip() if description.strip() else None,
        )
        result.cash_transactions.append(cash)

    def _merge_fractional_trades(self, transactions: list[ParsedTransaction]) -> list[ParsedTransaction]:
        """Merge fractional trades: TR splits orders into whole + fractional parts."""
        merged: dict[tuple, ParsedTransaction] = {}
        order: list[tuple] = []

        for tx in transactions:
            key = (tx.date, tx.isin, tx.transaction_type)
            if key in merged:
                existing = merged[key]
                total_cost = (existing.quantity * existing.price_per_share) + \
                             (tx.quantity * tx.price_per_share)
                existing.quantity = round(existing.quantity + tx.quantity, 6)
                if existing.quantity > 0:
                    existing.price_per_share = round(total_cost / existing.quantity, 6)
                existing.source_id = f"TR-{tx.date}-{tx.isin}-{tx.transaction_type}-{existing.quantity}"
            else:
                merged[key] = ParsedTransaction(
                    date=tx.date,
                    broker=tx.broker,
                    transaction_type=tx.transaction_type,
                    name=tx.name,
                    ticker=tx.ticker,
                    isin=tx.isin,
                    quantity=tx.quantity,
                    price_per_share=tx.price_per_share,
                    currency=tx.currency,
                    fees=tx.fees,
                    taxes=tx.taxes,
                    exchange_rate=tx.exchange_rate,
                    fees_currency=tx.fees_currency,
                    notes=tx.notes,
                    source_id=tx.source_id,
                )
                order.append(key)

        return [merged[k] for k in order]
