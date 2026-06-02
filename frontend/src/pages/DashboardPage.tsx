import { FileSearch, LogOut, FileText, Moon, Sun, MessageSquare, BarChart3, Zap } from 'lucide-react';
import { ReactNode } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { useDocuments } from '../hooks/useDocuments';
import { useDashboardStats } from '../hooks/useQueries';
import UploadZone from '../components/dashboard/UploadZone';
import DocumentCard from '../components/dashboard/DocumentCard';
import EmptyState from '../components/shared/EmptyState';

export default function DashboardPage() {
  const { logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { data: documents, isLoading } = useDocuments();
  const { data: stats } = useDashboardStats();

  return (
    <div className="min-h-screen bg-stone-50 dark:bg-stone-950 transition-colors">
      <header className="bg-white dark:bg-stone-900 border-b border-stone-200 dark:border-stone-800">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <FileSearch className="w-6 h-6 text-accent-500" />
            <h1 className="text-lg font-bold text-stone-900 dark:text-stone-100">DocLens</h1>
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className="p-2 text-stone-400 hover:text-stone-600 dark:hover:text-stone-300 rounded-lg hover:bg-stone-100 dark:hover:bg-stone-800 transition-colors"
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
            <button
              onClick={logout}
              className="flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-700 dark:text-stone-400 dark:hover:text-stone-200 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Dashboard Stats */}
        {stats && (stats.total_documents > 0 || stats.total_queries > 0) && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
            <StatCard icon={<FileText className="w-4 h-4" />} label="Documents" value={stats.total_documents} />
            <StatCard icon={<MessageSquare className="w-4 h-4" />} label="Questions" value={stats.total_queries} />
            <StatCard
              icon={<BarChart3 className="w-4 h-4" />}
              label="Avg Confidence"
              value={`${stats.avg_confidence_pct}%`}
            />
            <StatCard
              icon={<Zap className="w-4 h-4" />}
              label="Budget Left"
              value={`${stats.budget_remaining_pct}%`}
              accent={stats.budget_remaining_pct < 20}
            />
          </div>
        )}

        <div className="mb-8">
          <h2 className="text-xl font-semibold text-stone-800 dark:text-stone-200 mb-4">Upload a document</h2>
          <UploadZone />
        </div>

        <div>
          <h2 className="text-xl font-semibold text-stone-800 dark:text-stone-200 mb-4">Your documents</h2>

          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : !documents || documents.length === 0 ? (
            <EmptyState
              icon={<FileText className="w-12 h-12" />}
              title="No documents yet"
              description="Upload a PDF or text file above to get started."
            />
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <DocumentCard key={doc.id} doc={doc} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function StatCard({ icon, label, value, accent }: {
  icon: ReactNode;
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 rounded-xl p-3 transition-colors">
      <div className="flex items-center gap-1.5 text-xs text-stone-500 dark:text-stone-400 mb-1">
        {icon}
        {label}
      </div>
      <p className={`text-lg font-semibold ${accent ? 'text-amber-500' : 'text-stone-800 dark:text-stone-100'}`}>
        {value}
      </p>
    </div>
  );
}
