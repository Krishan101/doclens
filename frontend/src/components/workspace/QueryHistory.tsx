import { useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquare } from 'lucide-react';
import type { QueryHistoryItem } from '../../types';

export default function QueryHistory({ items }: { items: QueryHistoryItem[] }) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-stone-500 uppercase tracking-wide">Previous Questions</p>
      {items.map((item) => (
        <HistoryItem key={item.id} item={item} />
      ))}
    </div>
  );
}

function HistoryItem({ item }: { item: QueryHistoryItem }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-stone-200 rounded-lg overflow-hidden bg-white">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-stone-50 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-stone-400 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-stone-400 flex-shrink-0" />
        )}
        <MessageSquare className="w-3.5 h-3.5 text-stone-400 flex-shrink-0" />
        <span className="text-sm text-stone-700 truncate">{item.question}</span>
        <span className="ml-auto text-xs text-stone-400 flex-shrink-0">
          {item.source_count} sources
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 text-sm text-stone-600 border-t border-stone-100 pt-2">
          {item.answer}
        </div>
      )}
    </div>
  );
}
