import { useState } from 'react';
import { Search } from 'lucide-react';
import { useAskQuestion, useQueryHistory } from '../../hooks/useQueries';
import { useHighlight } from '../../context/HighlightContext';
import type { QueryResult } from '../../types';
import QueryInput from './QueryInput';
import ActiveAnswer from './ActiveAnswer';
import QueryHistory from './QueryHistory';
import EmptyState from '../shared/EmptyState';

interface QueryPanelProps {
  documentId: string;
}

export default function QueryPanel({ documentId }: QueryPanelProps) {
  const [activeResult, setActiveResult] = useState<QueryResult | null>(null);
  const askQuestion = useAskQuestion();
  const { data: history } = useQueryHistory(documentId);
  const { setHighlights, clearHighlights } = useHighlight();

  const handleAsk = (question: string) => {
    clearHighlights();
    setActiveResult(null);

    askQuestion.mutate(
      { document_id: documentId, question },
      {
        onSuccess: (result) => {
          setActiveResult(result);
          // Highlight source chunks in the document view with keyword matching
          const chunkIds = result.sources.map((s) => s.chunk_id);
          setHighlights(chunkIds, question);
        },
      }
    );
  };

  return (
    <div className="h-full flex flex-col bg-stone-50 border-l border-stone-200">
      <div className="p-4 border-b border-stone-200 bg-white">
        <QueryInput
          onSubmit={handleAsk}
          isLoading={askQuestion.isPending}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {askQuestion.isPending && (
          <div className="bg-white border border-stone-200 rounded-xl p-4 animate-pulse">
            <div className="h-3 bg-stone-200 rounded w-1/3 mb-3" />
            <div className="space-y-2">
              <div className="h-3 bg-stone-100 rounded w-full" />
              <div className="h-3 bg-stone-100 rounded w-5/6" />
              <div className="h-3 bg-stone-100 rounded w-4/6" />
            </div>
          </div>
        )}

        {askQuestion.isError && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            {(askQuestion.error as any)?.response?.data?.detail || 'Something went wrong. Please try again.'}
          </div>
        )}

        {activeResult && <ActiveAnswer result={activeResult} />}

        {!activeResult && !askQuestion.isPending && (!history || history.length === 0) && (
          <EmptyState
            icon={<Search className="w-10 h-10" />}
            title="Ask your first question"
            description="Type a question about this document and get an AI-generated answer with source references."
          />
        )}

        {history && history.length > 0 && (
          <QueryHistory items={history.filter((h) => h.id !== activeResult?.id)} />
        )}
      </div>
    </div>
  );
}
