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
  getBrokerDetails,
  updateBrokerCash,
  updateBrokerAccountType,
  getCashSummary,
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
  uploadImportFile,
  confirmImport,
  getDividendCalendar,
  getMovers,
  getStockAlerts,
  createAlert,
  updateAlert as updateAlertApi,
  deleteAlert as deleteAlertApi,
} from '@/api/client';
import type { TransactionCreate, DividendCreate, StockInfoCreate, ManualPriceCreate, ImportConfirmPayload, BrokerCashUpdate, StockAlertCreate } from '@/types';

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

export const useMovers = (period: string) => {
  return useQuery({
    queryKey: ['movers', period],
    queryFn: () => getMovers(period),
    enabled: period !== '1d',
    staleTime: 15 * 60 * 1000, // 15 minutes
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

export const useDividendCalendar = () => {
  return useQuery({
    queryKey: ['dividends', 'calendar'],
    queryFn: getDividendCalendar,
    staleTime: 30 * 60 * 1000,
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
      queryClient.invalidateQueries({ queryKey: ['stock', variables.ticker] });
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

export const useBrokerDetails = () => {
  return useQuery({
    queryKey: ['brokers', 'details'],
    queryFn: getBrokerDetails,
    staleTime: 5 * 60 * 1000,
  });
};

export const useUpdateBrokerCash = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ brokerName, data }: { brokerName: string; data: BrokerCashUpdate }) =>
      updateBrokerCash(brokerName, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
      queryClient.invalidateQueries({ queryKey: ['cashSummary'] });
    },
  });
};

export const useUpdateBrokerAccountType = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ brokerName, accountType }: { brokerName: string; accountType: string }) =>
      updateBrokerAccountType(brokerName, accountType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
    },
  });
};

export const useCashSummary = () => {
  return useQuery({
    queryKey: ['cashSummary'],
    queryFn: getCashSummary,
    staleTime: 5 * 60 * 1000,
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

// =============================================================================
// Import Hooks
// =============================================================================

export const useUploadImportFile = () => {
  return useMutation({
    mutationFn: ({ file, broker }: { file: File; broker?: string }) =>
      uploadImportFile(file, broker),
  });
};

export const useConfirmImport = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: ImportConfirmPayload) => confirmImport(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dividends'] });
      queryClient.invalidateQueries({ queryKey: ['stocks'] });
      queryClient.invalidateQueries({ queryKey: ['brokers'] });
      queryClient.invalidateQueries({ queryKey: ['analysis'] });
    },
  });
};

// =============================================================================
// Stock Alert Hooks
// =============================================================================

export const useStockAlerts = (ticker: string) => {
  return useQuery({
    queryKey: ['alerts', ticker],
    queryFn: () => getStockAlerts(ticker),
    enabled: !!ticker,
  });
};

export const useCreateAlert = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (alert: StockAlertCreate) => createAlert(alert),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['alerts', variables.ticker] });
    },
  });
};

export const useUpdateAlert = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ alertId, data }: { alertId: number; data: StockAlertCreate }) =>
      updateAlertApi(alertId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['alerts', variables.data.ticker] });
    },
  });
};

export const useDeleteAlert = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ alertId }: { alertId: number; ticker: string }) =>
      deleteAlertApi(alertId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['alerts', variables.ticker] });
    },
  });
};
