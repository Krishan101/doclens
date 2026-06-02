import { useNavigate } from 'react-router-dom';
import { ArrowLeft, FileSearch, Moon, Sun } from 'lucide-react';
import type { Document } from '../../types';
import { useTheme } from '../../context/ThemeContext';
import BudgetIndicator from './BudgetIndicator';

export default function WorkspaceHeader({ doc }: { doc: Document }) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="px-4 lg:px-6 py-3 bg-white dark:bg-stone-900 border-b border-stone-200 dark:border-stone-800 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="p-1.5 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <FileSearch className="w-5 h-5 text-accent-500" />
            <span className="text-sm font-semibold text-stone-800 dark:text-stone-100">{doc.filename}</span>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <BudgetIndicator />
          <div className="flex items-center gap-3 text-xs text-stone-500 dark:text-stone-400">
            {doc.page_count && <span>{doc.page_count} pages</span>}
            {doc.chunk_count != null && <span>{doc.chunk_count} chunks</span>}
          </div>
          <button
            onClick={toggleTheme}
            className="p-1.5 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Document summary */}
      {doc.summary && (
        <p className="mt-2 ml-10 text-xs text-stone-500 dark:text-stone-400 leading-relaxed line-clamp-2">
          {doc.summary}
        </p>
      )}
    </header>
  );
}
