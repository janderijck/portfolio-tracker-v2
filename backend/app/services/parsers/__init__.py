"""
Broker file parsers for importing transactions from various platforms.

Supported brokers:
- Saxo Bank (XLSX export)
- DEGIRO (CSV export)
- Trade Republic (PDF account statement)
- Bolero (PDF portfolio report)
"""
from .base import BaseParser, ParseResult
from .saxo import SaxoParser
from .degiro import DegiroParser
from .traderepublic import TradeRepublicParser
from .bolero import BoleroParser

PARSERS = {
    "saxo": SaxoParser,
    "degiro": DegiroParser,
    "traderepublic": TradeRepublicParser,
    "bolero": BoleroParser,
}


def detect_broker(filename: str) -> str | None:
    """Auto-detect broker from filename patterns."""
    filename_lower = filename.lower()
    if "transactions" in filename_lower and filename_lower.endswith(".xlsx"):
        return "saxo"
    if "degiro" in filename_lower and filename_lower.endswith(".csv"):
        return "degiro"
    if "rekeningoverzicht" in filename_lower and filename_lower.endswith(".pdf"):
        return "traderepublic"
    if "bolero" in filename_lower and filename_lower.endswith(".pdf"):
        return "bolero"
    return None


def get_parser(broker: str) -> BaseParser:
    """Get parser instance for a broker."""
    parser_class = PARSERS.get(broker.lower())
    if not parser_class:
        raise ValueError(f"No parser available for broker: {broker}")
    return parser_class()
