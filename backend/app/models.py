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
    FUND = "FUND"


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
    quantity: float
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
    stock_name: Optional[str] = None

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
    quantity: float
    avg_purchase_price: float
    total_invested: float
    total_invested_eur: float
    total_fees: float
    currency: str
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    current_value_eur: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_percent: Optional[float] = None
    change_percent: Optional[float] = None
    is_usd_account: bool = False
    manual_price_date: Optional[date] = None
    pays_dividend: bool = False
    sentiment_bullish_pct: Optional[float] = None


class PortfolioSummary(BaseModel):
    total_invested_eur: float
    total_current_value_eur: float
    total_gain_loss_eur: float
    total_gain_loss_percent: float


class PortfolioResponse(BaseModel):
    holdings: List[PortfolioHolding]
    summary: PortfolioSummary
    prices_updated_at: Optional[str] = None


# =============================================================================
# Movers Models (Response only - calculated at runtime)
# =============================================================================

class MoverItem(BaseModel):
    ticker: str
    name: str
    change_percent: float


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
# Dividend Calendar Models (Response only - calculated at runtime)
# =============================================================================

class DividendForecastItem(BaseModel):
    ticker: str
    isin: str
    ex_date: date
    estimated_amount: float
    currency: str
    frequency: str
    is_forecast: bool = True
    stock_name: Optional[str] = None


class MonthlyDividendSummary(BaseModel):
    month: str
    received: float
    forecasted: float


class DividendCalendarResponse(BaseModel):
    historical: List[Dividend]
    forecasted: List[DividendForecastItem]
    monthly_summary: List[MonthlyDividendSummary]


# =============================================================================
# User Settings Models
# =============================================================================

class UserSettings(BaseModel):
    date_format: str = "DD/MM/YYYY"
    finnhub_api_key: Optional[str] = None
    openfigi_api_key: Optional[str] = None
    saxo_connected: bool = False


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


# =============================================================================
# Saxo Integration Models
# =============================================================================

class SaxoConfig(BaseModel):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    auth_url: str = ""
    token_url: str = ""


class SaxoPosition(BaseModel):
    uic: int
    isin: Optional[str] = None
    name: str
    quantity: float
    current_price: float
    current_value: float
    currency: str
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    matched_ticker: Optional[str] = None
    symbol: Optional[str] = None
    exchange_id: Optional[str] = None


class SaxoBalance(BaseModel):
    total_value: float
    cash_balance: float
    positions_value: float
    unrealized_pnl: float
    currency: str


class SaxoDividendSyncResult(BaseModel):
    imported: int = 0
    skipped_duplicate: int = 0
    skipped_unmatched: int = 0
    errors: List[str] = []
    ca_endpoint_available: bool = True


class SaxoSyncResult(BaseModel):
    positions: List[SaxoPosition]
    balance: SaxoBalance
    matched: int
    unmatched: int
    missing_local: int
    dividends: Optional[SaxoDividendSyncResult] = None


class SaxoImportRequest(BaseModel):
    positions: List[SaxoPosition]


class SaxoImportResult(BaseModel):
    imported_stocks: int
    imported_transactions: int
    skipped: int
    errors: List[str]


# =============================================================================
# IBKR Integration Models
# =============================================================================

class IBKRConfig(BaseModel):
    flex_token: str = ""
    query_id: str = ""


class IBKRSyncResult(BaseModel):
    transactions_imported: int = 0
    dividends_imported: int = 0
    cash_imported: int = 0
    stocks_created: int = 0
    positions_found: int = 0
    warnings: List[str] = []
    errors: List[str] = []


class IBKRStatus(BaseModel):
    configured: bool = False
    has_token: bool = False
    has_query_id: bool = False
    last_sync: Optional[str] = None


# =============================================================================
# Broker Cash Models
# =============================================================================

class BrokerCashBalance(BaseModel):
    currency: str
    balance: float


class BrokerDetail(BaseModel):
    broker_name: str
    country: str = "België"
    has_w8ben: bool = False
    w8ben_expiry_date: Optional[str] = None
    cash_balances: List[BrokerCashBalance] = []
    account_type: str = "Privé"
    notes: Optional[str] = None


class BrokerCreate(BaseModel):
    broker_name: str


class BrokerAccountTypeUpdate(BaseModel):
    account_type: str


class BrokerCashUpdate(BaseModel):
    currency: str = "EUR"
    balance: float


class BrokerCashItem(BaseModel):
    broker_name: str
    cash_balance: float
    cash_currency: str
    cash_balance_eur: float


class CashSummary(BaseModel):
    total_cash_eur: float
    per_broker: List[BrokerCashItem]


# =============================================================================
# Import Models
# =============================================================================

class ImportConfirmRequest(BaseModel):
    transactions: list = []
    dividends: list = []
    cash_transactions: list = []
    stocks: list = []


# =============================================================================
# Telegram & Alert Models
# =============================================================================

class TelegramConfig(BaseModel):
    bot_token: str = ""
    chat_id: str = ""


class StockAlertCreate(BaseModel):
    ticker: str
    alert_type: str  # 'period_high', 'period_low', 'above', 'below'
    period: Optional[str] = None  # '52w', '26w', '13w'
    threshold_price: Optional[float] = None
    enabled: bool = True


class StockAlert(StockAlertCreate):
    id: int
    last_triggered_at: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class AlertCheckResult(BaseModel):
    checked: int = 0
    triggered: int = 0
    errors: List[str] = []
