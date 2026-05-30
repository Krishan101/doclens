import { useMemo } from 'react';
import { useHighlight } from '../../context/HighlightContext';

interface ChunkBlockProps {
  id: string;
  content: string;
  chunkType: 'text' | 'table';
  pageNumber: number | null;
  chunkIndex: number;
}

const STOP_WORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
  'on', 'with', 'at', 'by', 'from', 'as', 'into', 'about', 'between',
  'through', 'after', 'before', 'above', 'below', 'and', 'but', 'or',
  'not', 'no', 'nor', 'so', 'yet', 'both', 'each', 'all', 'any',
  'it', 'its', 'this', 'that', 'these', 'those', 'what', 'which',
  'who', 'whom', 'how', 'when', 'where', 'why', 'i', 'me', 'my',
  'we', 'our', 'you', 'your', 'he', 'she', 'they', 'them', 'their',
]);

function extractKeywords(query: string): string[] {
  return query
    .toLowerCase()
    .replace(/[^\w\s]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 2 && !STOP_WORDS.has(w));
}

function highlightText(content: string, keywords: string[]): React.ReactNode[] {
  if (keywords.length === 0) return [content];

  // Build regex matching any keyword (case-insensitive)
  const pattern = new RegExp(`(${keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
  const parts = content.split(pattern);

  return parts.map((part, i) => {
    const isMatch = keywords.some(k => part.toLowerCase() === k.toLowerCase());
    if (isMatch) {
      return (
        <mark key={i} className="bg-accent-300 text-stone-900 rounded-sm px-0.5">
          {part}
        </mark>
      );
    }
    return part;
  });
}

export default function ChunkBlock({ id, content, chunkType }: ChunkBlockProps) {
  const { highlightedChunkIds, activeChunkId, searchQuery } = useHighlight();
  const isHighlighted = highlightedChunkIds.has(id);
  const isActive = activeChunkId === id;

  const keywords = useMemo(() => {
    if (!isHighlighted || !searchQuery) return [];
    return extractKeywords(searchQuery);
  }, [isHighlighted, searchQuery]);

  const renderedContent = useMemo(() => {
    if (!isHighlighted || keywords.length === 0) return content;
    return highlightText(content, keywords);
  }, [content, isHighlighted, keywords]);

  return (
    <div
      id={`chunk-${id}`}
      className={`relative py-2 px-3 rounded-lg transition-all duration-300
        ${isHighlighted ? 'bg-accent-50 border-l-[3px] border-l-accent-500' : 'border-l-[3px] border-l-transparent'}
        ${isActive ? 'animate-highlight-pulse ring-2 ring-accent-300' : ''}
      `}
    >
      {chunkType === 'table' ? (
        <div className="overflow-x-auto">
          <pre className="text-xs font-mono text-stone-700 whitespace-pre-wrap">{renderedContent}</pre>
        </div>
      ) : (
        <p className="text-sm font-mono text-stone-700 leading-relaxed whitespace-pre-wrap">{renderedContent}</p>
      )}
    </div>
  );
}
