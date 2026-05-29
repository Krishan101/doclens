import { useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, FileSearch } from 'lucide-react';
import type { Document } from '../../types';

export default function WorkspaceHeader({ doc }: { doc: Document }) {
  const navigate = useNavigate();

  return (
    <header className="flex items-center justify-between px-4 lg:px-6 py-3 bg-white border-b border-stone-200">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/')}
          className="p-1.5 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100 transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <FileSearch className="w-5 h-5 text-accent-500" />
          <span className="text-sm font-semibold text-stone-800">{doc.filename}</span>
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-stone-500">
        {doc.page_count && <span>{doc.page_count} pages</span>}
        {doc.chunk_count != null && <span>{doc.chunk_count} chunks</span>}
      </div>
    </header>
  );
}
