import { useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import type { Chunk } from '../../types';
import ChunkBlock from './ChunkBlock';
import EmptyState from '../shared/EmptyState';

interface DocumentPanelProps {
  chunks: Chunk[] | undefined;
  isLoading: boolean;
}

/**
 * Remove overlapping text between adjacent chunks.
 * Chunks have ~150 char overlap from the chunking algorithm.
 * We trim the overlapping prefix from each chunk after the first.
 */
function deduplicateChunks(chunks: Chunk[]): (Chunk & { displayContent: string })[] {
  if (chunks.length === 0) return [];

  const result: (Chunk & { displayContent: string })[] = [
    { ...chunks[0], displayContent: chunks[0].content },
  ];

  for (let i = 1; i < chunks.length; i++) {
    const prev = chunks[i - 1];
    const curr = chunks[i];

    // Skip table chunks — no overlap dedup needed
    if (curr.chunk_type === 'table' || prev.chunk_type === 'table') {
      result.push({ ...curr, displayContent: curr.content });
      continue;
    }

    // Find overlap: check if start of current matches end of previous
    let overlapLen = 0;
    const maxOverlap = Math.min(200, prev.content.length, curr.content.length);

    for (let len = maxOverlap; len >= 20; len--) {
      const prevEnd = prev.content.slice(-len).trim();
      const currStart = curr.content.slice(0, len).trim();
      if (prevEnd === currStart) {
        overlapLen = len;
        break;
      }
    }

    if (overlapLen > 0) {
      result.push({ ...curr, displayContent: curr.content.slice(overlapLen).trim() });
    } else {
      result.push({ ...curr, displayContent: curr.content });
    }
  }

  return result;
}

export default function DocumentPanel({ chunks, isLoading }: DocumentPanelProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-6 h-6 text-stone-400 animate-spin" />
      </div>
    );
  }

  if (!chunks || chunks.length === 0) {
    return <EmptyState title="No content" description="This document has no extractable text." />;
  }

  const dedupedChunks = useMemo(() => deduplicateChunks(chunks), [chunks]);

  let currentPage: number | null = null;

  return (
    <div className="h-full overflow-y-auto p-4 lg:p-6 space-y-1">
      {dedupedChunks.map((chunk) => {
        const showPageBreak = chunk.page_number !== currentPage && chunk.page_number != null;
        currentPage = chunk.page_number;

        // Skip chunks that became empty after dedup
        if (!chunk.displayContent.trim()) return null;

        return (
          <div key={chunk.id}>
            {showPageBreak && (
              <div className="flex items-center gap-3 py-3">
                <div className="flex-1 h-px bg-stone-200" />
                <span className="text-xs text-stone-400 font-medium">Page {chunk.page_number}</span>
                <div className="flex-1 h-px bg-stone-200" />
              </div>
            )}
            <ChunkBlock
              id={chunk.id}
              content={chunk.displayContent}
              chunkType={chunk.chunk_type}
              pageNumber={chunk.page_number}
              chunkIndex={chunk.chunk_index}
            />
          </div>
        );
      })}
    </div>
  );
}
