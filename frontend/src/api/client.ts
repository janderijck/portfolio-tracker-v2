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
  MoverItem,
  PerformanceSummary,
  DividendSummary,
  CostSummary,
  AllocationSummary,
  UserSettings,
  ManualPrice,
  ManualPriceCreate,
  ImportPreviewResponse,
  ImportConfirmPayload,
  ImportConfirmResponse,
  DividendCalendarResponse,
  BrokerDetail,
  BrokerCashUpdate,
  CashSummary,
  SaxoConfig,
  SaxoPosition,
  SaxoBalance,
  SaxoSyncResult,
  SaxoStatus,
  SaxoImportRequest,
  SaxoImportResult,
  IBKRConfig,
  IBKRSyncResult,
  IBKRStatus,
  TelegramConfig,
  StockAlert,
  StockAlertCreate,
  AlertCheckResult,
  HistoricalDataPoint,
  WatchlistItem,
  StockDetailResponse,
  StockLookupResult,
  StockSearchResult,
} from '@/types';

// Use environment variable for API URL, fallback to /api for local development
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
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

export const refreshPrices = async (): Promise<{ refreshed: number; total: number; errors: string[] }> => {
  const { data } = await api.post('/prices/refresh');
  return data;
};

export const getMovers = async (period: string): Promise<MoverItem[]> => {
  const { data } = await api.get('/movers', { params: { period } });
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

export const getDividendCalendar = async (): Promise<DividendCalendarResponse> => {
  const { data } = await api.get('/dividends/calendar');
  return data;
};

// =============================================================================
// Stocks
// =============================================================================

export const getStocks = async (): Promise<StockInfo[]> => {
  const { data } = await api.get('/stocks');
  return data;
};

export const getWatchlist = async (): Promise<WatchlistItem[]> => {
  const { data } = await api.get('/watchlist');
  return data;
};

export const getStockDetail = async (ticker: string): Promise<StockDetailResponse> => {
  const { data } = await api.get(`/stocks/${ticker}`);
  return data;
};

export const createStock = async (stock: StockInfoCreate): Promise<StockInfo> => {
  const { data } = await api.post('/stocks', stock);
  return data;
};

export const lookupStockByISIN = async (isin: string): Promise<StockLookupResult> => {
  const { data } = await api.get(`/stocks/lookup/${isin}`);
  return data;
};

export const searchStocks = async (query: string): Promise<StockSearchResult[]> => {
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

export const getBrokerDetails = async (): Promise<BrokerDetail[]> => {
  const { data } = await api.get('/brokers/details');
  return data;
};

export const updateBrokerCash = async (brokerName: string, cashData: BrokerCashUpdate): Promise<void> => {
  await api.put(`/brokers/${encodeURIComponent(brokerName)}/cash`, cashData);
};

export const updateBrokerAccountType = async (brokerName: string, accountType: string): Promise<void> => {
  await api.put(`/brokers/${encodeURIComponent(brokerName)}/account-type`, { account_type: accountType });
};

export const getCashSummary = async (): Promise<CashSummary> => {
  const { data } = await api.get('/brokers/cash-summary');
  return data;
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

export const getPortfolioEvolution = async (broker?: string): Promise<{ date: string; gain: number; invested: number; value: number }[]> => {
  const params = broker ? { broker } : {};
  const { data } = await api.get('/analysis/portfolio-evolution', { params });
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

export const resetDatabase = async (): Promise<{ message: string }> => {
  const { data } = await api.delete('/database/reset');
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

export const getStockHistory = async (ticker: string, period: string = '1y'): Promise<HistoricalDataPoint[]> => {
  const { data } = await api.get(`/stocks/${ticker}/history`, { params: { period } });
  return data;
};

// =============================================================================
// Import
// =============================================================================

export const uploadImportFile = async (file: File, broker?: string): Promise<ImportPreviewResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  if (broker) {
    formData.append('broker', broker);
  }
  const { data } = await api.post('/import/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const confirmImport = async (payload: ImportConfirmPayload): Promise<ImportConfirmResponse> => {
  const { data } = await api.post('/import/confirm', payload);
  return data;
};

// =============================================================================
// Saxo Integration
// =============================================================================

export const getSaxoConfig = async (): Promise<SaxoConfig> => {
  const { data } = await api.get('/saxo/config');
  return data;
};

export const saveSaxoConfig = async (config: SaxoConfig): Promise<SaxoConfig> => {
  const { data } = await api.put('/saxo/config', config);
  return data;
};

export const getSaxoAuthUrl = async (): Promise<{ url: string; state: string }> => {
  const { data } = await api.get('/saxo/auth-url');
  return data;
};

export const saxoCallback = async (code: string): Promise<{ success: boolean; message: string; account?: any }> => {
  const { data } = await api.post('/saxo/callback', { code });
  return data;
};

export const disconnectSaxo = async (): Promise<{ success: boolean }> => {
  const { data } = await api.post('/saxo/disconnect');
  return data;
};

export const testSaxoConnection = async (): Promise<{ success: boolean; message: string; account?: any }> => {
  const { data } = await api.post('/saxo/test');
  return data;
};

export const getSaxoPositions = async (): Promise<SaxoPosition[]> => {
  const { data } = await api.get('/saxo/positions');
  return data;
};

export const getSaxoBalances = async (): Promise<SaxoBalance> => {
  const { data } = await api.get('/saxo/balances');
  return data;
};

export const syncSaxo = async (): Promise<SaxoSyncResult> => {
  const { data } = await api.post('/saxo/sync');
  return data;
};

export const importSaxoPositions = async (payload: SaxoImportRequest): Promise<SaxoImportResult> => {
  const { data } = await api.post('/saxo/import-positions', payload);
  return data;
};

export const getSaxoStatus = async (): Promise<SaxoStatus> => {
  const { data } = await api.get('/saxo/status');
  return data;
};

// =============================================================================
// IBKR Integration
// =============================================================================

export const getIBKRConfig = async (): Promise<IBKRConfig> => {
  const { data } = await api.get('/ibkr/config');
  return data;
};

export const saveIBKRConfig = async (config: IBKRConfig): Promise<IBKRConfig> => {
  const { data } = await api.put('/ibkr/config', config);
  return data;
};

export const testIBKRConnection = async (): Promise<{ success: boolean; message: string; account?: any }> => {
  const { data } = await api.post('/ibkr/test');
  return data;
};

export const syncIBKR = async (): Promise<IBKRSyncResult> => {
  const { data } = await api.post('/ibkr/sync');
  return data;
};

export const disconnectIBKR = async (): Promise<{ success: boolean }> => {
  const { data } = await api.post('/ibkr/disconnect');
  return data;
};

export const getIBKRStatus = async (): Promise<IBKRStatus> => {
  const { data } = await api.get('/ibkr/status');
  return data;
};

// =============================================================================
// Telegram
// =============================================================================

export const getTelegramConfig = async (): Promise<TelegramConfig> => {
  const { data } = await api.get('/telegram/config');
  return data;
};

export const saveTelegramConfig = async (config: TelegramConfig): Promise<TelegramConfig> => {
  const { data } = await api.put('/telegram/config', config);
  return data;
};

export const testTelegram = async (): Promise<{ success: boolean; message: string }> => {
  const { data } = await api.post('/telegram/test');
  return data;
};

export const disconnectTelegram = async (): Promise<{ success: boolean }> => {
  const { data } = await api.post('/telegram/disconnect');
  return data;
};

// =============================================================================
// Stock Alerts
// =============================================================================

export const getStockAlerts = async (ticker: string): Promise<StockAlert[]> => {
  const { data } = await api.get(`/alerts/${ticker}`);
  return data;
};

export const createAlert = async (alert: StockAlertCreate): Promise<StockAlert> => {
  const { data } = await api.post('/alerts', alert);
  return data;
};

export const updateAlert = async (alertId: number, alert: StockAlertCreate): Promise<StockAlert> => {
  const { data } = await api.put(`/alerts/${alertId}`, alert);
  return data;
};

export const deleteAlert = async (alertId: number): Promise<void> => {
  await api.delete(`/alerts/${alertId}`);
};

export const checkAlerts = async (): Promise<AlertCheckResult> => {
  const { data } = await api.post('/alerts/check');
  return data;
};

export default api;
