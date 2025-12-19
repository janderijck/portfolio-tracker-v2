/**
 * React Query hooks for portfolio data.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPortfolio,
  getTransactions,
  getDividends,
  getStocks,
  getWatchlist,
  createTransaction,
  updateTransaction,
  deleteTransaction,
  createDividend,
  updateDividend,
  deleteDividend,
  createStock,
  updateStock,
  deleteStock,
  getBrokers,
  getPerformanceSummary,
  getDividendSummary,
  getCostSummary,
  getAllocationSummary,
  getManualPrices,
  createManualPrice,
  updateManualPrice,
  deleteManualPrice,
  getStockDetail,
  getStockHistory,
} from '@/api/client';
import type { TransactionCreate, DividendCreate, StockInfoCreate, ManualPriceCreate } from '@/types';

// =============================================================================
// Portfolio Hooks
// =============================================================================

export const usePortfolio = () => {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

// =============================================================================
// Transaction Hooks
// =============================================================================

export const useTransactions = (ticker?: string) => {
  return useQuery({
    queryKey: ['transactions', ticker],
    queryFn: () => getTransactions(ticker),
  });
};

export const useCreateTransaction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
};

export const useUpdateTransaction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TransactionCreate }) =>
      updateTransaction(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
};

export const useDeleteTransaction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
    },
  });
};

// =============================================================================
// Dividend Hooks
// =============================================================================

export const useDividends = (ticker?: string) => {
  return useQuery({
    queryKey: ['dividends', ticker],
    queryFn: () => getDividends(ticker),
  });
};

export const useCreateDividend = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createDividend,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
    },
  });
};

export const useUpdateDividend = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: DividendCreate }) =>
      updateDividend(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
    },
  });
};

export const useDeleteDividend = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteDividend,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
    },
  });
};

// =============================================================================
// Stock Hooks
// =============================================================================

export const useStocks = () => {
  return useQuery({
    queryKey: ['stocks'],
    queryFn: getStocks,
  });
};

export const useWatchlist = () => {
  return useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
  });
};

export const useCreateStock = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (stock: StockInfoCreate) => createStock(stock),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stocks'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
};

export const useUpdateStock = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticker, stock }: { ticker: string; stock: StockInfoCreate }) =>
      updateStock(ticker, stock),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['stocks'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['stockDetail', variables.ticker] });
    },
  });
};

export const useDeleteStock = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteStock,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stocks'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
    },
  });
};

// =============================================================================
// Broker Hooks
// =============================================================================

export const useBrokers = () => {
  return useQuery({
    queryKey: ['brokers'],
    queryFn: getBrokers,
    staleTime: 60 * 60 * 1000, // 1 hour - brokers rarely change
  });
};

// =============================================================================
// Analysis Hooks
// =============================================================================

export const usePerformance = () => {
  return useQuery({
    queryKey: ['analysis', 'performance'],
    queryFn: getPerformanceSummary,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useDividendSummary = () => {
  return useQuery({
    queryKey: ['analysis', 'dividends'],
    queryFn: getDividendSummary,
    staleTime: 5 * 60 * 1000,
  });
};

export const useCosts = () => {
  return useQuery({
    queryKey: ['analysis', 'costs'],
    queryFn: getCostSummary,
    staleTime: 5 * 60 * 1000,
  });
};

export const useAllocation = () => {
  return useQuery({
    queryKey: ['analysis', 'allocation'],
    queryFn: getAllocationSummary,
    staleTime: 5 * 60 * 1000,
  });
};

// =============================================================================
// Stock Detail Hooks
// =============================================================================

export const useStockDetail = (ticker: string) => {
  return useQuery({
    queryKey: ['stock', ticker],
    queryFn: () => getStockDetail(ticker),
  });
};

export const useStockHistory = (ticker: string, period: string = '1y') => {
  return useQuery({
    queryKey: ['stockHistory', ticker, period],
    queryFn: () => getStockHistory(ticker, period),
    staleTime: 1000 * 60 * 60, // 1 hour cache
  });
};

// =============================================================================
// Manual Price Hooks
// =============================================================================

export const useManualPrices = (ticker: string) => {
  return useQuery({
    queryKey: ['manualPrices', ticker],
    queryFn: () => getManualPrices(ticker),
  });
};

export const useCreateManualPrice = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticker, data }: { ticker: string; data: ManualPriceCreate }) =>
      createManualPrice(ticker, data),
    onSuccess: (_, { ticker }) => {
      queryClient.invalidateQueries({ queryKey: ['manualPrices', ticker] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['stock', ticker] });
    },
  });
};

export const useUpdateManualPrice = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticker, id, data }: { ticker: string; id: number; data: ManualPriceCreate }) =>
      updateManualPrice(ticker, id, data),
    onSuccess: (_, { ticker }) => {
      queryClient.invalidateQueries({ queryKey: ['manualPrices', ticker] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['stock', ticker] });
    },
  });
};

export const useDeleteManualPrice = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ticker, id }: { ticker: string; id: number }) =>
      deleteManualPrice(ticker, id),
    onSuccess: (_, { ticker }) => {
      queryClient.invalidateQueries({ queryKey: ['manualPrices', ticker] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['stock', ticker] });
    },
  });
};
