export interface PortfolioHolding {
  ticker: string;
  isin: string;
  name: string;
  broker: string;
  quantity: number;
  avg_purchase_price: number;
  avg_purchase_price_eur: number;
  total_invested: number;
  total_invested_eur: number;
  total_fees: number;
  total_fees_eur: number;
  currency: string;
  current_price: number | null;
  current_value: number | null;
  gain_loss: number | null;
  gain_loss_percent: number | null;
  dividends_received: number;
  is_usd_account: boolean;
}

export interface PortfolioSummary {
  total_invested_eur: number;
  total_current_value_eur: number;
  total_gain_loss_eur: number;
  total_gain_loss_percent: number;
  total_dividends_eur: number;
  total_invested_usd: number | null;
  total_current_value_usd: number | null;
  total_gain_loss_usd: number | null;
  total_dividends_usd: number | null;
  has_usd_holdings: boolean;
}

export interface PortfolioResponse {
  holdings: PortfolioHolding[];
  summary: PortfolioSummary;
}

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

export interface Dividend {
  id: number;
  ticker: string;
  isin: string;
  ex_date: string;
  bruto_amount: number;
  currency: string;
  notes: string | null;
  received: boolean;
  tax_paid: boolean;
  withheld_amount: number | null;
  additional_tax_due: number | null;
  net_received: number | null;
}

export interface DividendSummary {
  total_bruto: number;
  total_tax: number;
  total_netto: number;
  count: number;
  received_count: number;
  currency: string;
}

export interface CashFlowSummary {
  broker: string;
  deposits: number;
  withdrawals: number;
  net_deposited: number;
  purchases: number;
  sales: number;
  dividends: number;
  expected_cash: number;
  portfolio_value: number;
  total_value: number;
  currency: string;
  deposits_usd: number | null;
  cash_usd: number | null;
  fx_gain_loss: number | null;
}

export interface FXAnalysis {
  broker: string;
  source_currency: string;
  dest_currency: string;
  original_amount: number;
  current_value_eur: number;
  gain_loss: number;
  avg_rate_at_deposit: number;
  current_rate: number;
}

export interface CostBreakdown {
  broker: string;
  total_fees: number;
  total_taxes: number;
  total_costs: number;
  transaction_count: number;
}
