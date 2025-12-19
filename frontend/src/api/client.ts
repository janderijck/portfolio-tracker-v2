/**
 * API client for Portfolio Tracker backend.
 *
 * This module contains only API calls - no business logic.
 */
import axios from 'axios';
import type {
  PortfolioResponse,
  Transaction,
  TransactionCreate,
  Dividend,
  DividendCreate,
  StockInfo,
  StockInfoCreate,
  PerformanceSummary,
  DividendSummary,
  CostSummary,
  AllocationSummary,
  UserSettings,
  ManualPrice,
  ManualPriceCreate,
} from '@/types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// =============================================================================
// Portfolio
// =============================================================================

export const getPortfolio = async (): Promise<PortfolioResponse> => {
  const { data } = await api.get('/portfolio');
  return data;
};

// =============================================================================
// Transactions
// =============================================================================

export const getTransactions = async (ticker?: string): Promise<Transaction[]> => {
  const params = ticker ? { ticker } : {};
  const { data } = await api.get('/transactions', { params });
  return data;
};

export const createTransaction = async (transaction: TransactionCreate): Promise<Transaction> => {
  const { data } = await api.post('/transactions', transaction);
  return data;
};

export const updateTransaction = async (id: number, transaction: TransactionCreate): Promise<Transaction> => {
  const { data } = await api.put(`/transactions/${id}`, transaction);
  return data;
};

export const deleteTransaction = async (id: number): Promise<void> => {
  await api.delete(`/transactions/${id}`);
};

// =============================================================================
// Dividends
// =============================================================================

export const getDividends = async (ticker?: string): Promise<Dividend[]> => {
  const params = ticker ? { ticker } : {};
  const { data } = await api.get('/dividends', { params });
  return data;
};

export const createDividend = async (dividend: DividendCreate): Promise<Dividend> => {
  const { data } = await api.post('/dividends', dividend);
  return data;
};

export const updateDividend = async (id: number, dividend: DividendCreate): Promise<Dividend> => {
  const { data } = await api.put(`/dividends/${id}`, dividend);
  return data;
};

export const deleteDividend = async (id: number): Promise<void> => {
  await api.delete(`/dividends/${id}`);
};

export const fetchDividendHistory = async (ticker: string): Promise<{ message: string; count: number; total_found: number }> => {
  const { data } = await api.post(`/dividends/fetch-history/${ticker}`);
  return data;
};

// =============================================================================
// Stocks
// =============================================================================

export const getStocks = async (): Promise<StockInfo[]> => {
  const { data } = await api.get('/stocks');
  return data;
};

export const getWatchlist = async () => {
  const { data } = await api.get('/watchlist');
  return data;
};

export const getStockDetail = async (ticker: string) => {
  const { data } = await api.get(`/stocks/${ticker}`);
  return data;
};

export const createStock = async (stock: StockInfoCreate): Promise<StockInfo> => {
  const { data } = await api.post('/stocks', stock);
  return data;
};

export const lookupStockByISIN = async (isin: string) => {
  const { data } = await api.get(`/stocks/lookup/${isin}`);
  return data;
};

export const searchStocks = async (query: string) => {
  const { data } = await api.get('/stocks/search', { params: { q: query } });
  return data;
};

export const updateStock = async (ticker: string, stock: StockInfoCreate): Promise<StockInfo> => {
  const { data } = await api.put(`/stocks/${ticker}`, stock);
  return data;
};

export const deleteStock = async (ticker: string): Promise<void> => {
  await api.delete(`/stocks/${ticker}`);
};

// =============================================================================
// Brokers
// =============================================================================

export const getBrokers = async (): Promise<string[]> => {
  const { data } = await api.get('/brokers');
  return data;
};

export const createBroker = async (name: string): Promise<void> => {
  await api.post('/brokers', { broker_name: name });
};

// =============================================================================
// Analysis
// =============================================================================

export const getPerformanceSummary = async (): Promise<PerformanceSummary> => {
  const { data } = await api.get('/analysis/performance');
  return data;
};

export const getDividendSummary = async (): Promise<DividendSummary> => {
  const { data } = await api.get('/analysis/dividends');
  return data;
};

export const getCostSummary = async (): Promise<CostSummary> => {
  const { data } = await api.get('/analysis/costs');
  return data;
};

export const getAllocationSummary = async (): Promise<AllocationSummary> => {
  const { data } = await api.get('/analysis/allocation');
  return data;
};

// =============================================================================
// User Settings
// =============================================================================

export const getSettings = async (): Promise<UserSettings> => {
  const { data } = await api.get('/settings');
  return data;
};

export const updateSettings = async (settings: UserSettings): Promise<UserSettings> => {
  const { data } = await api.put('/settings', settings);
  return data;
};

export const testFinnhubApi = async (): Promise<{ success: boolean; message: string; test_data?: any }> => {
  const { data } = await api.post('/settings/test-finnhub');
  return data;
};

// =============================================================================
// Manual Prices
// =============================================================================

export const getManualPrices = async (ticker: string): Promise<ManualPrice[]> => {
  const { data } = await api.get(`/stocks/${ticker}/prices`);
  return data;
};

export const createManualPrice = async (ticker: string, price: ManualPriceCreate): Promise<ManualPrice> => {
  const { data } = await api.post(`/stocks/${ticker}/prices`, price);
  return data;
};

export const updateManualPrice = async (ticker: string, id: number, price: ManualPriceCreate): Promise<ManualPrice> => {
  const { data } = await api.put(`/stocks/${ticker}/prices/${id}`, price);
  return data;
};

export const deleteManualPrice = async (ticker: string, id: number): Promise<void> => {
  await api.delete(`/stocks/${ticker}/prices/${id}`);
};

// =============================================================================
// Historical Data
// =============================================================================

export interface HistoricalDataPoint {
  date: string;
  price: number;
}

export const getStockHistory = async (ticker: string, period: string = '1y'): Promise<HistoricalDataPoint[]> => {
  const { data } = await api.get(`/stocks/${ticker}/history`, { params: { period } });
  return data;
};

export default api;
