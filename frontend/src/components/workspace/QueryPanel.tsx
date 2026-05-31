import { useState, useRef } from 'react';
import { Search, Sparkles, Loader2 } from 'lucide-react';
import { useQueryHistory, useSuggestions } from '../../hooks/useQueries';
import { useStreamingQuery } from '../../hooks/useStreamingQuery';
import { useHighlight } from '../../context/HighlightContext';
import QueryInput, { QueryInputRef } from './QueryInput';
import ConfidenceBadge from './ConfidenceBadge';
import SourcePill from './SourcePill';
import AnswerActions from './AnswerActions';
import QueryHistory from './QueryHistory';

interface QueryPanelProps {
  documentId: string;
}

export default function QueryPanel({ documentId }: QueryPanelProps) {
  const [lastQuestion, setLastQuestion] = useState('');
  const queryInputRef = useRef<QueryInputRef>(null);
  const {
    stream, reset, isStreaming, streamedAnswer,
    sources, confidence, error, isDone, finalResult,
  } = useStreamingQuery();
  const { data: history } = useQueryHistory(documentId);
  const { data: suggestionsData, isLoading: suggestionsLoading } = useSuggestions(documentId);
  const { setHighlights, clearHighlights } = useHighlight();

  const handleAsk = (question: string) => {
    clearHighlights();
    reset();
    setLastQuestion(question);
    stream(documentId, question);
  };

  // Highlight sources as soon as they arrive
  if (sources.length > 0) {
    const chunkIds = sources.map((s) => s.chunk_id);
    setHighlights(chunkIds, lastQuestion);
  }

  const suggestions = suggestionsData?.suggestions || [];
  const showSuggestions = !isStreaming && !streamedAnswer && !isDone && suggestions.length > 0;
  const hasActiveAnswer = streamedAnswer || isDone;

  const fallbackQuestions = [
    "What is the main topic of this document?",
    "Summarize the key findings",
    "What are the most important numbers or dates?",
  ];

  return (
    <div className="h-full flex flex-col bg-stone-50 border-l border-stone-200">
      <div className="p-4 border-b border-stone-200 bg-white">
        <QueryInput
          ref={queryInputRef}
          onSubmit={handleAsk}
          isLoading={isStreaming}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Streaming/completed answer */}
        {hasActiveAnswer && (
          <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-3 animate-slide-up">
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-stone-500 uppercase tracking-wide">Answer</p>
              {confidence && <ConfidenceBadge confidence={confidence as any} />}
            </div>

            <div className="text-sm text-stone-800 leading-relaxed border-l-[3px] border-l-amber-500 pl-3">
              {streamedAnswer}
              {isStreaming && (
                <span className="inline-block w-0.5 h-4 bg-stone-700 animate-pulse ml-0.5 align-middle" />
              )}
            </div>

            {sources.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {sources.map((source, i) => (
                  <SourcePill key={source.chunk_id} source={source} index={i} />
                ))}
              </div>
            )}

            {isDone && finalResult && (
              <>
                <div className="flex items-center gap-3 text-xs text-stone-400 pt-1">
                  {finalResult.latency_ms && <span>{((finalResult.latency_ms as number) / 1000).toFixed(1)}s</span>}
                  {finalResult.model_used && <span>{(finalResult.model_used as string).split('-').slice(0, 2).join(' ')}</span>}
                  {(finalResult as any).budget && (
                    <span className="flex items-center gap-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        (finalResult as any).budget.remaining_pct > 50 ? 'bg-green-500' :
                        (finalResult as any).budget.remaining_pct > 20 ? 'bg-amber-500' : 'bg-red-500'
                      }`} />
                      {(finalResult as any).budget.remaining_pct}% budget
                    </span>
                  )}
                </div>

                <AnswerActions
                  answer={streamedAnswer}
                  sources={sources}
                  onRegenerate={() => handleAsk(lastQuestion)}
                  onFollowUp={() => {
                    queryInputRef.current?.setValue('Tell me more about ');
                    queryInputRef.current?.focus();
                  }}
                />
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            {error?.detail?.message || error?.detail || 'Something went wrong. Please try again.'}
          </div>
        )}

        {/* Suggested questions */}
        {showSuggestions && (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-xs font-medium text-stone-500 uppercase tracking-wide">
              <Sparkles className="w-3.5 h-3.5" />
              Suggested Questions
            </div>
            <div className="space-y-2">
              {suggestions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleAsk(q)}
                  className="w-full text-left px-3 py-2.5 bg-white border border-stone-200 rounded-lg
                    text-sm text-stone-700 hover:border-amber-300 hover:bg-amber-50 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {suggestionsLoading && !hasActiveAnswer && (
          <div className="flex items-center gap-2 text-xs text-stone-400 py-4 justify-center">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Generating suggested questions...
          </div>
        )}

        {/* Fallback questions */}
        {!showSuggestions && !hasActiveAnswer && !isStreaming && !suggestionsLoading && suggestions.length === 0 && (
          <div className="space-y-2 pt-4">
            <p className="text-xs text-stone-400">Try asking...</p>
            {fallbackQuestions.map((q, i) => (
              <button
                key={i}
                onClick={() => handleAsk(q)}
                className="w-full text-left px-3 py-2 border border-stone-200 rounded-lg text-sm
                  text-stone-500 hover:text-stone-700 hover:border-stone-300 hover:bg-stone-50 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* History */}
        {history && history.length > 0 && (
          <QueryHistory items={history} />
        )}
      </div>
    </div>
  );
}
