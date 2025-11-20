from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class TransactionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class CashTransactionType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"


class AssetType(str, Enum):
    STOCK = "STOCK"
    REIT = "REIT"


# Transaction Models
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


# Dividend Models
class DividendBase(BaseModel):
    ticker: str
    isin: str
    ex_date: date
    bruto_amount: float
    currency: str = "USD"
    notes: Optional[str] = None
    received: bool = False
    tax_paid: bool = False
    withheld_amount: Optional[float] = None
    additional_tax_due: Optional[float] = None
    net_received: Optional[float] = None


class DividendCreate(DividendBase):
    pass


class Dividend(DividendBase):
    id: int

    class Config:
        from_attributes = True


class DividendSummary(BaseModel):
    total_bruto: float
    total_tax: float
    total_netto: float
    count: int
    received_count: int
    currency: str = "EUR"


# Cash Transaction Models
class CashTransactionBase(BaseModel):
    date: date
    broker: str
    transaction_type: CashTransactionType
    amount: float
    currency: str = "EUR"
    source_amount: Optional[float] = None
    source_currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    notes: Optional[str] = None


class CashTransactionCreate(CashTransactionBase):
    pass


class CashTransaction(CashTransactionBase):
    id: int

    class Config:
        from_attributes = True


# Portfolio Models
class PortfolioHolding(BaseModel):
    ticker: str
    isin: str
    name: str
    broker: str
    quantity: int
    avg_purchase_price: float
    avg_purchase_price_eur: float
    total_invested: float
    total_invested_eur: float
    total_fees: float
    total_fees_eur: float
    currency: str
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_percent: Optional[float] = None
    dividends_received: float = 0.0
    is_usd_account: bool = False


class PortfolioSummary(BaseModel):
    total_invested_eur: float
    total_current_value_eur: float
    total_gain_loss_eur: float
    total_gain_loss_percent: float
    total_dividends_eur: float
    # USD section (if applicable)
    total_invested_usd: Optional[float] = None
    total_current_value_usd: Optional[float] = None
    total_gain_loss_usd: Optional[float] = None
    total_dividends_usd: Optional[float] = None
    has_usd_holdings: bool = False


# Broker Models
class BrokerSettings(BaseModel):
    broker_name: str
    country: str = "België"
    has_w8ben: bool = False
    w8ben_expiry_date: Optional[date] = None
    notes: Optional[str] = None


# Stock Info Models
class StockInfo(BaseModel):
    ticker: str
    isin: str
    name: str
    asset_type: AssetType = AssetType.STOCK
    country: str = "Verenigde Staten"
    custom_dividend_tax_rate: Optional[float] = None
    yahoo_ticker: Optional[str] = None


# Tax Calculation Models
class TaxCalculation(BaseModel):
    bruto_amount: float
    us_withholding: float
    belgian_tax: float
    total_tax: float
    net_amount: float
    effective_rate: float
    breakdown: str


# Cash Flow Models
class CashFlowSummary(BaseModel):
    broker: str
    deposits: float
    withdrawals: float
    net_deposited: float
    purchases: float
    sales: float
    dividends: float
    expected_cash: float
    portfolio_value: float
    total_value: float
    currency: str = "EUR"
    # USD specific (for USD accounts)
    deposits_usd: Optional[float] = None
    cash_usd: Optional[float] = None
    fx_gain_loss: Optional[float] = None


# FX Analysis Models
class FXAnalysis(BaseModel):
    broker: str
    source_currency: str
    dest_currency: str
    original_amount: float
    current_value_eur: float
    gain_loss: float
    avg_rate_at_deposit: float
    current_rate: float


# API Response Models
class PortfolioResponse(BaseModel):
    holdings: List[PortfolioHolding]
    summary: PortfolioSummary


class StockDetailResponse(BaseModel):
    info: StockInfo
    holding: Optional[PortfolioHolding]
    transactions: List[Transaction]
    dividends: List[Dividend]
    dividend_summary: DividendSummary


# CSV Upload Models
class CSVUploadResponse(BaseModel):
    success: bool
    message: str
    imported_count: int
    errors: List[str] = []


# Price Models
class PriceInfo(BaseModel):
    ticker: str
    current_price: float
    change_percent: float
    currency: str
    updated_at: datetime


class ExchangeRate(BaseModel):
    from_currency: str
    to_currency: str
    rate: float
    updated_at: datetime
