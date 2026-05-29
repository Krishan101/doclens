import { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface HighlightContextType {
  highlightedChunkIds: Set<string>;
  activeChunkId: string | null;
  setHighlights: (chunkIds: string[]) => void;
  scrollToChunk: (chunkId: string) => void;
  clearHighlights: () => void;
}

const HighlightContext = createContext<HighlightContextType | null>(null);

export function HighlightProvider({ children }: { children: ReactNode }) {
  const [highlightedChunkIds, setHighlightedChunkIds] = useState<Set<string>>(new Set());
  const [activeChunkId, setActiveChunkId] = useState<string | null>(null);

  const setHighlights = useCallback((chunkIds: string[]) => {
    setHighlightedChunkIds(new Set(chunkIds));
    setActiveChunkId(null);
  }, []);

  const scrollToChunk = useCallback((chunkId: string) => {
    setActiveChunkId(chunkId);
    const el = document.getElementById(`chunk-${chunkId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, []);

  const clearHighlights = useCallback(() => {
    setHighlightedChunkIds(new Set());
    setActiveChunkId(null);
  }, []);

  return (
    <HighlightContext.Provider value={{ highlightedChunkIds, activeChunkId, setHighlights, scrollToChunk, clearHighlights }}>
      {children}
    </HighlightContext.Provider>
  );
}

export function useHighlight() {
  const ctx = useContext(HighlightContext);
  if (!ctx) throw new Error('useHighlight must be used within HighlightProvider');
  return ctx;
}
