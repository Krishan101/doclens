import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';
import type { Document, Chunk } from '../types';

export function useDocuments() {
  return useQuery<Document[]>({
    queryKey: ['documents'],
    queryFn: async () => {
      const res = await api.get('/documents');
      return res.data;
    },
  });
}

export function useDocument(id: string | undefined) {
  return useQuery<Document>({
    queryKey: ['document', id],
    queryFn: async () => {
      const res = await api.get(`/documents/${id}`);
      return res.data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      // Poll while processing
      const data = query.state.data;
      return data?.status === 'processing' ? 2000 : false;
    },
  });
}

export function useDocumentChunks(id: string | undefined, enabled: boolean = true) {
  return useQuery<{ chunks: Chunk[] }>({
    queryKey: ['document-chunks', id],
    queryFn: async () => {
      const res = await api.get(`/documents/${id}/chunks`);
      return res.data;
    },
    enabled: !!id && enabled,
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post('/documents', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data as Document;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/documents/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}
