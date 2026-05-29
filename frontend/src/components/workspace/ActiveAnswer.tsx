import type { QueryResult } from '../../types';
import ConfidenceBadge from './ConfidenceBadge';
import SourcePill from './SourcePill';

export default function ActiveAnswer({ result }: { result: QueryResult }) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-stone-500 uppercase tracking-wide">Answer</p>
        <ConfidenceBadge confidence={result.confidence} />
      </div>

      <div className="text-sm text-stone-800 leading-relaxed border-l-[3px] border-l-accent-500 pl-3">
        {result.answer}
      </div>

      {result.sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {result.sources.map((source, i) => (
            <SourcePill key={source.chunk_id} source={source} index={i} />
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 text-xs text-stone-400 pt-1">
        {result.latency_ms && <span>{(result.latency_ms / 1000).toFixed(1)}s</span>}
        {result.model_used && result.model_used !== 'none' && (
          <span>{result.model_used.split('-').slice(0, 2).join(' ')}</span>
        )}
        {result.budget && (
          <span className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full ${
              result.budget.remaining_pct > 50 ? 'bg-green-500' :
              result.budget.remaining_pct > 20 ? 'bg-amber-500' : 'bg-red-500'
            }`} />
            {result.budget.remaining_pct}% budget
          </span>
        )}
      </div>
    </div>
  );
}
