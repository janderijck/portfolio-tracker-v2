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
}

export type DividendCreate = Omit<Dividend, 'id'>;

// =============================================================================
// Stock Info Types
// =============================================================================

export interface StockInfo {
  id: number;
  ticker: string;
  isin: string;
  name: string;
  asset_type: 'STOCK' | 'REIT';
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
  gain_loss: number | null;
  gain_loss_percent: number | null;
  is_usd_account: boolean;
  manual_price_date: string | null;
  pays_dividend: boolean;
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
