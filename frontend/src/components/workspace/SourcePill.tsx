import { useHighlight } from '../../context/HighlightContext';
import type { SourceChunk } from '../../types';

export default function SourcePill({ source, index }: { source: SourceChunk; index: number }) {
  const { scrollToChunk } = useHighlight();

  return (
    <button
      onClick={() => scrollToChunk(source.chunk_id)}
      className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md
        bg-accent-100 text-accent-700 hover:bg-accent-200 transition-colors cursor-pointer
        animate-[slide-up_0.2s_ease-out_both]"
      style={{ animationDelay: `${index * 60}ms` }}
      title={`Similarity: ${(source.similarity * 100).toFixed(0)}%${source.bm25_score ? ` | BM25: ${source.bm25_score.toFixed(3)}` : ''}`}
    >
      <span>Source {index + 1}</span>
      {source.page_number && <span className="text-accent-500">· p.{source.page_number}</span>}
      {source.bm25_score != null && source.bm25_score > 0 && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400" title="Keyword match" />
      )}
    </button>
  );
}
