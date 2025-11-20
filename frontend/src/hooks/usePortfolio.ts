import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPortfolio,
  getTransactions,
  getDividends,
  getCashFlow,
  getFXAnalysis,
  getCosts,
  createTransaction,
  deleteTransaction,
  createDividend,
  deleteDividend,
} from '@/api/client';

export const usePortfolio = () => {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useTransactions = (ticker?: string) => {
  return useQuery({
    queryKey: ['transactions', ticker],
    queryFn: () => getTransactions(ticker),
  });
};

export const useDividends = (ticker?: string) => {
  return useQuery({
    queryKey: ['dividends', ticker],
    queryFn: () => getDividends(ticker),
  });
};

export const useCashFlow = (broker?: string) => {
  return useQuery({
    queryKey: ['cashFlow', broker],
    queryFn: () => getCashFlow(broker),
  });
};

export const useFXAnalysis = (broker?: string) => {
  return useQuery({
    queryKey: ['fxAnalysis', broker],
    queryFn: () => getFXAnalysis(broker),
  });
};

export const useCosts = () => {
  return useQuery({
    queryKey: ['costs'],
    queryFn: getCosts,
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
