import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, FileSearch, Moon, Sun, ChevronDown, ChevronUp } from 'lucide-react';
import type { Document } from '../../types';
import { useTheme } from '../../context/ThemeContext';
import BudgetIndicator from './BudgetIndicator';

export default function WorkspaceHeader({ doc }: { doc: Document }) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const [summaryExpanded, setSummaryExpanded] = useState(false);

  return (
    <header className="px-4 lg:px-6 py-3 bg-white border-b border-stone-200 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="p-1.5 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
          >
            <FileSearch className="w-5 h-5 text-accent-500" />
            <span className="text-sm font-semibold text-stone-800">DocLens</span>
          </button>
          <span className="text-stone-300">|</span>
          <span className="text-sm text-stone-600 truncate max-w-[200px]">{doc.filename}</span>
        </div>

        <div className="flex items-center gap-4">
          <BudgetIndicator />
          <div className="hidden md:flex items-center gap-3 text-xs text-stone-500">
            {doc.page_count && <span>{doc.page_count} pages</span>}
            {doc.chunk_count != null && <span>{doc.chunk_count} chunks</span>}
          </div>
          <button
            onClick={toggleTheme}
            className="p-1.5 text-stone-400 hover:text-stone-600 rounded-lg hover:bg-stone-100 transition-colors"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Document summary — collapsible */}
      {doc.summary && (
        <div className="mt-2 ml-10">
          <p className={`text-xs text-stone-500 leading-relaxed ${summaryExpanded ? '' : 'line-clamp-2'}`}>
            {doc.summary}
          </p>
          {doc.summary.length > 150 && (
            <button
              onClick={() => setSummaryExpanded(!summaryExpanded)}
              className="flex items-center gap-0.5 text-xs text-accent-600 hover:text-accent-700 mt-0.5"
            >
              {summaryExpanded ? <><ChevronUp className="w-3 h-3" /> Less</> : <><ChevronDown className="w-3 h-3" /> More</>}
            </button>
          )}
        </div>
      )}
    </header>
  );
}
