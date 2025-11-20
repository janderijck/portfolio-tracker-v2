import axios from 'axios';
import type {
  PortfolioResponse,
  PortfolioSummary,
  Transaction,
  Dividend,
  DividendSummary,
  CashFlowSummary,
  FXAnalysis,
  CostBreakdown,
} from '@/types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Portfolio
export const getPortfolio = async (): Promise<PortfolioResponse> => {
  const { data } = await api.get('/portfolio');
  return data;
};

export const getPortfolioSummary = async (): Promise<PortfolioSummary> => {
  const { data } = await api.get('/portfolio/summary');
  return data;
};

// Transactions
export const getTransactions = async (ticker?: string): Promise<Transaction[]> => {
  const params = ticker ? { ticker } : {};
  const { data } = await api.get('/transactions', { params });
  return data;
};

export const createTransaction = async (transaction: Omit<Transaction, 'id'>): Promise<Transaction> => {
  const { data } = await api.post('/transactions', transaction);
  return data;
};

export const deleteTransaction = async (id: number): Promise<void> => {
  await api.delete(`/transactions/${id}`);
};

// Dividends
export const getDividends = async (ticker?: string): Promise<Dividend[]> => {
  const params = ticker ? { ticker } : {};
  const { data } = await api.get('/dividends', { params });
  return data;
};

export const createDividend = async (dividend: Omit<Dividend, 'id'>): Promise<Dividend> => {
  const { data } = await api.post('/dividends', dividend);
  return data;
};

export const deleteDividend = async (id: number): Promise<void> => {
  await api.delete(`/dividends/${id}`);
};

export const getDividendSummary = async (ticker: string): Promise<DividendSummary> => {
  const { data } = await api.get(`/dividends/summary/${ticker}`);
  return data;
};

// Stocks
export const getStockDetail = async (ticker: string) => {
  const { data } = await api.get(`/stocks/${ticker}`);
  return data;
};

// Cash Flow
export const getCashFlow = async (broker?: string): Promise<CashFlowSummary[]> => {
  const params = broker ? { broker } : {};
  const { data } = await api.get('/cash-flow', { params });
  return data;
};

// FX Analysis
export const getFXAnalysis = async (broker?: string): Promise<FXAnalysis[]> => {
  const params = broker ? { broker } : {};
  const { data } = await api.get('/fx-analysis', { params });
  return data;
};

// Costs
export const getCosts = async (): Promise<CostBreakdown[]> => {
  const { data } = await api.get('/costs');
  return data;
};

// CSV Upload
export const uploadCSV = async (file: File, broker: string) => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post(`/portfolio/upload?broker=${broker}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
};

export default api;
