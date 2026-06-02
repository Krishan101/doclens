import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';
import type { QueryResult, QueryHistoryItem, BudgetStatus } from '../types';

export function useAskQuestion() {
  const queryClient = useQueryClient();

  return useMutation<QueryResult, Error, { document_id: string; question: string }>({
    mutationFn: async (req) => {
      const res = await api.post('/queries', req);
      return res.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['query-history', variables.document_id] });
    },
  });
}

export function useQueryHistory(documentId: string | undefined) {
  return useQuery<QueryHistoryItem[]>({
    queryKey: ['query-history', documentId],
    queryFn: async () => {
      const res = await api.get('/queries', { params: { document_id: documentId } });
      return res.data;
    },
    enabled: !!documentId,
  });
}

export function useSuggestions(documentId: string | undefined) {
  return useQuery<{ suggestions: string[] }>({
    queryKey: ['suggestions', documentId],
    queryFn: async () => {
      const res = await api.get(`/documents/${documentId}/suggestions`);
      return res.data;
    },
    enabled: !!documentId,
    staleTime: 1000 * 60 * 30, // cache for 30 min
    retry: 1,
  });
}

export function useBudget() {
  return useQuery<BudgetStatus>({
    queryKey: ['budget'],
    queryFn: async () => {
      const res = await api.get('/budget');
      return res.data;
    },
    refetchInterval: 30000, // refresh every 30s
  });
}

export function useDashboardStats() {
  return useQuery<{
    total_documents: number;
    total_queries: number;
    avg_confidence_pct: number;
    positive_feedback_pct: number | null;
    total_feedback: number;
    budget_remaining_pct: number;
  }>({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const res = await api.get('/stats');
      return res.data;
    },
  });
}
