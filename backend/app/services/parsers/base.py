"""
Base parser class for broker file imports.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional
from io import BytesIO

import pdfplumber


# Country detection from ISIN prefix
ISIN_COUNTRY_MAP = {
    "US": "Verenigde Staten",
    "BE": "België",
    "NL": "Nederland",
    "FR": "Frankrijk",
    "DE": "Duitsland",
    "IE": "Ierland",
    "GB": "Verenigd Koninkrijk",
    "LU": "Luxemburg",
    "IT": "Italië",
    "ES": "Spanje",
    "CH": "Zwitserland",
    "CA": "Canada",
    "AU": "Australië",
    "JP": "Japan",
    "DK": "Denemarken",
    "SE": "Zweden",
    "NO": "Noorwegen",
    "FI": "Finland",
    "AT": "Oostenrijk",
    "PT": "Portugal",
}


def _country_from_isin(isin: str) -> str:
    """Determine country from ISIN prefix."""
    if isin and len(isin) >= 2:
        return ISIN_COUNTRY_MAP.get(isin[:2].upper(), "Onbekend")
    return "Onbekend"


def _extract_text(file_content: BytesIO, result: "ParseResult") -> str:
    """Extract text from a PDF file using pdfplumber."""
    pages_text = []
    try:
        with pdfplumber.open(file_content) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
    except Exception as e:
        result.warnings.append(f"Fout bij het lezen van PDF: {str(e)}")
        return ""
    return "\n".join(pages_text)


@dataclass
class ParsedTransaction:
    """A parsed transaction ready for import."""
    date: str  # ISO format date string
    broker: str
    transaction_type: str  # "BUY" or "SELL"
    name: str
    ticker: str
    isin: str
    quantity: float
    price_per_share: float
    currency: str = "EUR"
    fees: float = 0.0
    taxes: float = 0.0
    exchange_rate: float = 1.0
    fees_currency: str = "EUR"
    notes: Optional[str] = None
    # Import metadata
    source_id: Optional[str] = None  # Original transaction ID from broker
    is_duplicate: bool = False


@dataclass
class ParsedDividend:
    """A parsed dividend ready for import."""
    ticker: str
    isin: str
    ex_date: str  # ISO format date string
    bruto_amount: float
    currency: str = "EUR"
    withheld_tax: float = 0.0
    net_amount: Optional[float] = None
    received: bool = True
    notes: Optional[str] = None
    # Import metadata
    is_duplicate: bool = False


@dataclass
class ParsedCashTransaction:
    """A parsed cash transaction (deposit/withdrawal)."""
    date: str  # ISO format date string
    broker: str
    transaction_type: str  # "DEPOSIT", "WITHDRAWAL", "FX_CONVERSION", "INTEREST", "FEE"
    amount: float
    currency: str = "EUR"
    source_amount: Optional[float] = None
    source_currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    notes: Optional[str] = None
    # Import metadata
    is_duplicate: bool = False


@dataclass
class ParsedStock:
    """A parsed stock info entry."""
    ticker: str
    isin: str
    name: str
    asset_type: str = "STOCK"  # "STOCK" or "ETF"
    currency: str = "EUR"
    yahoo_ticker: Optional[str] = None
    country: str = "Onbekend"
    manual_price_tracking: bool = False


@dataclass
class ParseResult:
    """Result of parsing a broker export file."""
    broker: str
    transactions: list[ParsedTransaction] = field(default_factory=list)
    dividends: list[ParsedDividend] = field(default_factory=list)
    cash_transactions: list[ParsedCashTransaction] = field(default_factory=list)
    stocks: list[ParsedStock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skipped_rows: int = 0


class BaseParser(ABC):
    """Abstract base class for broker file parsers."""

    @abstractmethod
    def parse(self, file_content: BytesIO, filename: str) -> ParseResult:
        """Parse a broker export file and return structured data."""
        pass

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        pass
