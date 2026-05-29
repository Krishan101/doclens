import { Loader2 } from 'lucide-react';
import type { Chunk } from '../../types';
import ChunkBlock from './ChunkBlock';
import EmptyState from '../shared/EmptyState';

interface DocumentPanelProps {
  chunks: Chunk[] | undefined;
  isLoading: boolean;
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

  // Group by page
  let currentPage: number | null = null;

  return (
    <div className="h-full overflow-y-auto p-4 lg:p-6 space-y-1">
      {chunks.map((chunk) => {
        const showPageBreak = chunk.page_number !== currentPage && chunk.page_number != null;
        currentPage = chunk.page_number;

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
              content={chunk.content}
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
