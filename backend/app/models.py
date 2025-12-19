"""
Pydantic models for API validation and serialization.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from enum import Enum


class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class AssetType(str, Enum):
    STOCK = "STOCK"
    REIT = "REIT"


# =============================================================================
# Transaction Models
# =============================================================================

class TransactionBase(BaseModel):
    date: date
    broker: str
    transaction_type: TransactionType
    name: str
    ticker: str
    isin: str
    quantity: int
    price_per_share: float
    currency: str = "EUR"
    fees: float = 0.0
    taxes: float = 0.0
    exchange_rate: float = 1.0
    fees_currency: str = "EUR"
    notes: Optional[str] = None


class TransactionCreate(TransactionBase):
    pass


class Transaction(TransactionBase):
    id: int

    class Config:
        from_attributes = True


# =============================================================================
# Dividend Models
# =============================================================================

class DividendBase(BaseModel):
    ticker: str
    isin: str
    ex_date: date
    bruto_amount: float
    currency: str = "USD"
    withheld_tax: float = 0.0
    net_amount: Optional[float] = None
    received: bool = False
    notes: Optional[str] = None


class DividendCreate(DividendBase):
    pass


class Dividend(DividendBase):
    id: int

    class Config:
        from_attributes = True


# =============================================================================
# Stock Info Models
# =============================================================================

class StockInfoBase(BaseModel):
    ticker: str
    isin: str
    name: str
    asset_type: AssetType = AssetType.STOCK
    country: str = "Verenigde Staten"
    yahoo_ticker: Optional[str] = None
    manual_price_tracking: bool = False
    pays_dividend: bool = False


class StockInfoCreate(StockInfoBase):
    pass


class StockInfo(StockInfoBase):
    id: int

    class Config:
        from_attributes = True


# =============================================================================
# Portfolio Models (Response only - calculated at runtime)
# =============================================================================

class PortfolioHolding(BaseModel):
    ticker: str
    isin: str
    name: str
    broker: str
    quantity: int
    avg_purchase_price: float
    total_invested: float
    total_invested_eur: float
    total_fees: float
    currency: str
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_percent: Optional[float] = None
    is_usd_account: bool = False
    manual_price_date: Optional[date] = None
    pays_dividend: bool = False


class PortfolioSummary(BaseModel):
    total_invested_eur: float
    total_current_value_eur: float
    total_gain_loss_eur: float
    total_gain_loss_percent: float


class PortfolioResponse(BaseModel):
    holdings: List[PortfolioHolding]
    summary: PortfolioSummary


# =============================================================================
# Analysis Models (Response only - calculated at runtime)
# =============================================================================

class PerformanceSummary(BaseModel):
    total_invested: float
    current_value: float
    total_gain_loss: float
    total_gain_loss_percent: float
    total_dividends: float
    total_return: float  # gain_loss + dividends
    total_return_percent: float
    best_performer: Optional[str] = None
    best_performer_percent: Optional[float] = None
    worst_performer: Optional[str] = None
    worst_performer_percent: Optional[float] = None


class DividendSummary(BaseModel):
    total_received: float
    total_withheld_tax: float
    total_net: float
    dividend_yield: float  # dividends / invested
    by_ticker: dict  # {ticker: {total: x, count: x}}
    by_year: dict  # {year: total}


class CostSummary(BaseModel):
    total_fees: float
    total_taxes: float
    transaction_count: int
    avg_fee_per_transaction: float
    by_broker: dict  # {broker: {total: x, count: x}}
    fees_as_percent_of_invested: float


class AllocationItem(BaseModel):
    name: str
    value: float
    percentage: float


class AllocationSummary(BaseModel):
    by_broker: List[AllocationItem]
    by_country: List[AllocationItem]
    by_asset_type: List[AllocationItem]


# =============================================================================
# User Settings Models
# =============================================================================

class UserSettings(BaseModel):
    date_format: str = "DD/MM/YYYY"
    finnhub_api_key: Optional[str] = None


# =============================================================================
# Manual Price Models
# =============================================================================

class ManualPriceBase(BaseModel):
    ticker: str
    date: date
    price: float
    currency: str = "EUR"
    notes: Optional[str] = None


class ManualPriceCreate(ManualPriceBase):
    pass


class ManualPrice(ManualPriceBase):
    id: int

    class Config:
        from_attributes = True
