import { useHighlight } from '../../context/HighlightContext';
import type { SourceChunk } from '../../types';

export default function SourcePill({ source, index }: { source: SourceChunk; index: number }) {
  const { scrollToChunk } = useHighlight();

  return (
    <button
      onClick={() => scrollToChunk(source.chunk_id)}
      className="inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md
        bg-accent-100 text-accent-700 hover:bg-accent-200 transition-colors cursor-pointer"
      title={`Similarity: ${(source.similarity * 100).toFixed(0)}%`}
    >
      <span>Source {index + 1}</span>
      {source.page_number && <span className="text-accent-500">· p.{source.page_number}</span>}
    </button>
  );
}
