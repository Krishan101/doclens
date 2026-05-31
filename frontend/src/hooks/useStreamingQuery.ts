import { useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { SourceChunk, QueryResult } from '../types';

export function useStreamingQuery() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedAnswer, setStreamedAnswer] = useState('');
  const [sources, setSources] = useState<SourceChunk[]>([]);
  const [confidence, setConfidence] = useState<string>('');
  const [error, setError] = useState<any | null>(null);
  const [isDone, setIsDone] = useState(false);
  const [finalResult, setFinalResult] = useState<Partial<QueryResult> | null>(null);
  const queryClient = useQueryClient();

  const stream = useCallback(async (documentId: string, question: string) => {
    setIsStreaming(true);
    setStreamedAnswer('');
    setSources([]);
    setConfidence('');
    setError(null);
    setIsDone(false);
    setFinalResult(null);

    const token = localStorage.getItem('doclens_token');

    try {
      const response = await fetch('/api/queries/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ document_id: documentId, question }),
      });

      if (!response.ok) {
        const err = await response.json();
        throw { status: response.status, detail: err.detail };
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));

            if (data.type === 'sources') {
              setSources(data.sources);
              setConfidence(data.confidence);
            } else if (data.type === 'token') {
              setStreamedAnswer((prev) => prev + data.token);
            } else if (data.type === 'done') {
              setFinalResult(data);
              setIsDone(true);
              queryClient.invalidateQueries({ queryKey: ['query-history', documentId] });
            } else if (data.type === 'error') {
              throw { status: 500, detail: data.error };
            }
          } catch (parseErr: any) {
            if (parseErr.status) throw parseErr;
          }
        }
      }
    } catch (err: any) {
      setError(err);
    } finally {
      setIsStreaming(false);
    }
  }, [queryClient]);

  const reset = useCallback(() => {
    setStreamedAnswer('');
    setSources([]);
    setConfidence('');
    setError(null);
    setIsDone(false);
    setFinalResult(null);
  }, []);

  return {
    stream, reset, isStreaming, streamedAnswer,
    sources, confidence, error, isDone, finalResult,
  };
}
