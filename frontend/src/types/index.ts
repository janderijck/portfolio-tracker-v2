/**
 * TypeScript types matching backend Pydantic models.
 */

// =============================================================================
// Transaction Types
// =============================================================================

export interface Transaction {
  id: number;
  date: string;
  broker: string;
  transaction_type: 'BUY' | 'SELL';
  name: string;
  ticker: string;
  isin: string;
  quantity: number;
  price_per_share: number;
  currency: string;
  fees: number;
  taxes: number;
  exchange_rate: number;
  fees_currency: string;
  notes: string | null;
}

export type TransactionCreate = Omit<Transaction, 'id'>;

// =============================================================================
// Dividend Types
// =============================================================================

export interface Dividend {
  id: number;
  ticker: string;
  isin: string;
  ex_date: string;
  bruto_amount: number;
  currency: string;
  withheld_tax: number;
  net_amount: number | null;
  received: boolean;
  notes: string | null;
  stock_name: string | null;
}

export type DividendCreate = Omit<Dividend, 'id' | 'stock_name'>;

// =============================================================================
// Stock Info Types
// =============================================================================

export interface StockInfo {
  id: number;
  ticker: string;
  isin: string;
  name: string;
  asset_type: 'STOCK' | 'REIT' | 'FUND';
  country: string;
  yahoo_ticker: string | null;
  manual_price_tracking: boolean;
  pays_dividend: boolean;
}

export type StockInfoCreate = Omit<StockInfo, 'id'>;

// =============================================================================
// Portfolio Types (calculated at runtime)
// =============================================================================

export interface PortfolioHolding {
  ticker: string;
  isin: string;
  name: string;
  broker: string;
  quantity: number;
  avg_purchase_price: number;
  total_invested: number;
  total_invested_eur: number;
  total_fees: number;
  currency: string;
  current_price: number | null;
  current_value: number | null;
  current_value_eur: number | null;
  gain_loss: number | null;
  gain_loss_percent: number | null;
  change_percent: number | null;
  is_usd_account: boolean;
  manual_price_date: string | null;
  pays_dividend: boolean;
  sentiment_bullish_pct: number | null;
}

export interface PortfolioSummary {
  total_invested_eur: number;
  total_current_value_eur: number;
  total_gain_loss_eur: number;
  total_gain_loss_percent: number;
}

export interface PortfolioResponse {
  holdings: PortfolioHolding[];
  summary: PortfolioSummary;
  prices_updated_at?: string;
}

// =============================================================================
// Movers Types (calculated at runtime)
// =============================================================================

export interface MoverItem {
  ticker: string;
  name: string;
  change_percent: number;
}

// =============================================================================
// Analysis Types (calculated at runtime)
// =============================================================================

export interface PerformanceSummary {
  total_invested: number;
  current_value: number;
  total_gain_loss: number;
  total_gain_loss_percent: number;
  total_dividends: number;
  total_return: number;
  total_return_percent: number;
  best_performer: string | null;
  best_performer_percent: number | null;
  worst_performer: string | null;
  worst_performer_percent: number | null;
}

export interface DividendSummary {
  total_received: number;
  total_withheld_tax: number;
  total_net: number;
  dividend_yield: number;
  by_ticker: Record<string, { total: number; count: number }>;
  by_year: Record<string, number>;
}

export interface CostSummary {
  total_fees: number;
  total_taxes: number;
  transaction_count: number;
  avg_fee_per_transaction: number;
  by_broker: Record<string, { total: number; count: number }>;
  fees_as_percent_of_invested: number;
}

export interface AllocationItem {
  name: string;
  value: number;
  percentage: number;
}

export interface AllocationSummary {
  by_broker: AllocationItem[];
  by_country: AllocationItem[];
  by_asset_type: AllocationItem[];
}

// =============================================================================
// User Settings Types
// =============================================================================

export interface UserSettings {
  date_format: string;
  finnhub_api_key?: string | null;
  openfigi_api_key?: string | null;
  saxo_connected?: boolean;
}

// =============================================================================
// Manual Price Types
// =============================================================================

export interface ManualPrice {
  id: number;
  ticker: string;
  date: string;
  price: number;
  currency: string;
  notes: string | null;
}

export type ManualPriceCreate = Omit<ManualPrice, 'id'>;

// =============================================================================
// Import Types
// =============================================================================

export interface ParsedTransaction {
  date: string;
  broker: string;
  transaction_type: 'BUY' | 'SELL';
  name: string;
  ticker: string;
  isin: string;
  quantity: number;
  price_per_share: number;
  currency: string;
  fees: number;
  taxes: number;
  exchange_rate: number;
  fees_currency: string;
  notes: string | null;
  source_id: string | null;
  is_duplicate: boolean;
}

export interface ParsedDividend {
  ticker: string;
  isin: string;
  ex_date: string;
  bruto_amount: number;
  currency: string;
  withheld_tax: number;
  net_amount: number | null;
  received: boolean;
  notes: string | null;
  is_duplicate: boolean;
}

export interface ParsedCashTransaction {
  date: string;
  broker: string;
  transaction_type: string;
  amount: number;
  currency: string;
  source_amount: number | null;
  source_currency: string | null;
  exchange_rate: number | null;
  notes: string | null;
  is_duplicate: boolean;
}

export interface ParsedStock {
  ticker: string;
  isin: string;
  name: string;
  asset_type: string;
  currency: string;
  yahoo_ticker: string | null;
  country: string;
  manual_price_tracking?: boolean;
}

export interface ImportPreviewSummary {
  total_transactions: number;
  total_dividends: number;
  total_cash: number;
  total_stocks: number;
  duplicate_transactions: number;
  duplicate_dividends: number;
}

export interface ImportPreviewResponse {
  broker: string;
  transactions: ParsedTransaction[];
  dividends: ParsedDividend[];
  cash_transactions: ParsedCashTransaction[];
  stocks: ParsedStock[];
  warnings: string[];
  skipped_rows: number;
  summary: ImportPreviewSummary;
}

export interface ImportConfirmPayload {
  transactions: ParsedTransaction[];
  dividends: ParsedDividend[];
  cash_transactions: ParsedCashTransaction[];
  stocks: ParsedStock[];
}

export interface ImportConfirmResponse {
  message: string;
  imported: {
    transactions: number;
    dividends: number;
    cash_transactions: number;
    stocks: number;
  };
  errors?: string[];
}

// =============================================================================
// Dividend Calendar Types
// =============================================================================

export interface DividendForecastItem {
  ticker: string;
  isin: string;
  ex_date: string;
  estimated_amount: number;
  currency: string;
  frequency: string;
  is_forecast: boolean;
  stock_name: string | null;
}

export interface MonthlyDividendSummary {
  month: string;
  received: number;
  forecasted: number;
}

export interface DividendCalendarResponse {
  historical: Dividend[];
  forecasted: DividendForecastItem[];
  monthly_summary: MonthlyDividendSummary[];
}

// =============================================================================
// Broker Cash Types
// =============================================================================

export interface BrokerCashBalance {
  currency: string;
  balance: number;
}

export interface BrokerDetail {
  broker_name: string;
  country: string;
  has_w8ben: boolean;
  w8ben_expiry_date: string | null;
  cash_balances: BrokerCashBalance[];
  account_type: string;
  notes: string | null;
}

export interface BrokerCashUpdate {
  currency: string;
  balance: number;
}

export interface BrokerCashItem {
  broker_name: string;
  cash_balance: number;
  cash_currency: string;
  cash_balance_eur: number;
}

export interface CashSummary {
  total_cash_eur: number;
  per_broker: BrokerCashItem[];
}

// =============================================================================
// Saxo Configuration Types
// =============================================================================

export interface SaxoConfig {
  client_id: string;
  client_secret: string;
  redirect_uri: string;
  auth_url: string;
  token_url: string;
}

// =============================================================================
// Saxo Integration Types
// =============================================================================

export interface SaxoPosition {
  uic: number;
  isin?: string | null;
  name: string;
  quantity: number;
  current_price: number;
  current_value: number;
  currency: string;
  pnl?: number | null;
  pnl_percent?: number | null;
  matched_ticker?: string | null;
  symbol?: string | null;
  exchange_id?: string | null;
}

export interface SaxoBalance {
  total_value: number;
  cash_balance: number;
  positions_value: number;
  unrealized_pnl: number;
  currency: string;
}

export interface SaxoDividendSyncResult {
  imported: number;
  skipped_duplicate: number;
  skipped_unmatched: number;
  errors: string[];
  ca_endpoint_available: boolean;
}

export interface SaxoSyncResult {
  positions: SaxoPosition[];
  balance: SaxoBalance;
  matched: number;
  unmatched: number;
  missing_local: number;
  dividends?: SaxoDividendSyncResult | null;
}

export interface SaxoStatus {
  connected: boolean;
  has_token: boolean;
  cached_prices: number;
  last_sync: string | null;
}

export interface SaxoImportRequest {
  positions: SaxoPosition[];
}

export interface SaxoImportResult {
  imported_stocks: number;
  imported_transactions: number;
  skipped: number;
  errors: string[];
}

// =============================================================================
// IBKR Integration Types
// =============================================================================

export interface IBKRConfig {
  flex_token: string;
  query_id: string;
}

export interface IBKRSyncResult {
  transactions_imported: number;
  dividends_imported: number;
  cash_imported: number;
  stocks_created: number;
  positions_found: number;
  warnings: string[];
  errors: string[];
}

export interface IBKRStatus {
  configured: boolean;
  has_token: boolean;
  has_query_id: boolean;
  last_sync: string | null;
}

// =============================================================================
// Telegram & Alert Types
// =============================================================================

export interface TelegramConfig {
  bot_token: string;
  chat_id: string;
}

export interface StockAlertCreate {
  ticker: string;
  alert_type: 'period_high' | 'period_low' | 'above' | 'below';
  period?: string | null;
  threshold_price?: number | null;
  enabled: boolean;
}

export interface StockAlert extends StockAlertCreate {
  id: number;
  last_triggered_at: string | null;
  created_at: string | null;
}

export interface AlertCheckResult {
  checked: number;
  triggered: number;
  errors: string[];
}

// =============================================================================
// Watchlist Types
// =============================================================================

export interface WatchlistItem {
  id: number;
  ticker: string;
  isin: string;
  name: string;
  asset_type: 'STOCK' | 'REIT' | 'FUND';
  country: string;
  yahoo_ticker: string | null;
  manual_price_tracking: boolean;
  pays_dividend: boolean;
  current_price: number | null;
  currency: string;
}

// =============================================================================
// Stock Detail Types
// =============================================================================

export interface PriceInfo {
  current_price: number;
  change_percent: number;
  currency: string;
}

export interface UpcomingDividend {
  ex_date: string;
  estimated_per_share: number;
  currency: string;
  frequency: string;
}

export interface StockTwitsSentiment {
  bullish: number;
  bearish: number;
  bullish_percent: number;
  message_count: number;
}

export interface StockDetailResponse {
  info: StockInfo | null;
  transactions: Transaction[];
  dividends: Dividend[];
  current_price: PriceInfo | null;
  upcoming_dividends: UpcomingDividend[];
  sentiment?: StockTwitsSentiment | null;
}

// =============================================================================
// Stock Lookup & Search Types
// =============================================================================

export interface StockLookupResult {
  ticker: string;
  isin: string;
  name: string;
  currency: string;
  country: string;
  asset_type: string;
  current_price: number | null;
  yahoo_ticker: string | null;
  pays_dividend: boolean;
  dividend_yield: number | null;
}

export interface StockSearchResult {
  ticker: string;
  isin: string;
  name: string;
  asset_type: string;
  country: string;
  yahoo_ticker: string | null;
  manual_price_tracking: boolean | number;
  current_price: number | null;
  currency: string;
  pays_dividend: boolean;
  dividend_yield: number | null;
  from_openfigi?: boolean;
  from_morningstar?: boolean;
}

// =============================================================================
// Historical Data Types
// =============================================================================

export interface HistoricalDataPoint {
  date: string;
  price: number;
}

