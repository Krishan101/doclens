import { useHighlight } from '../../context/HighlightContext';

interface ChunkBlockProps {
  id: string;
  content: string;
  chunkType: 'text' | 'table';
  pageNumber: number | null;
  chunkIndex: number;
}

export default function ChunkBlock({ id, content, chunkType, pageNumber, chunkIndex }: ChunkBlockProps) {
  const { highlightedChunkIds, activeChunkId } = useHighlight();
  const isHighlighted = highlightedChunkIds.has(id);
  const isActive = activeChunkId === id;

  return (
    <div
      id={`chunk-${id}`}
      className={`relative py-2 px-3 rounded-lg transition-all duration-300
        ${isHighlighted ? 'bg-accent-100 border-l-[3px] border-l-accent-500' : 'border-l-[3px] border-l-transparent'}
        ${isActive ? 'animate-highlight-pulse ring-2 ring-accent-300' : ''}
      `}
    >
      {chunkType === 'table' ? (
        <div className="overflow-x-auto">
          <pre className="text-xs font-mono text-stone-700 whitespace-pre-wrap">{content}</pre>
        </div>
      ) : (
        <p className="text-sm font-mono text-stone-700 leading-relaxed whitespace-pre-wrap">{content}</p>
      )}
    </div>
  );
}
