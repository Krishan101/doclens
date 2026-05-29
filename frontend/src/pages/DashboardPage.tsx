import { FileSearch, LogOut, FileText } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useDocuments } from '../hooks/useDocuments';
import UploadZone from '../components/dashboard/UploadZone';
import DocumentCard from '../components/dashboard/DocumentCard';
import EmptyState from '../components/shared/EmptyState';

export default function DashboardPage() {
  const { logout } = useAuth();
  const { data: documents, isLoading } = useDocuments();

  return (
    <div className="min-h-screen bg-stone-50">
      <header className="bg-white border-b border-stone-200">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileSearch className="w-6 h-6 text-accent-500" />
            <h1 className="text-lg font-bold text-stone-900">DocLens</h1>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-700 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-stone-800 mb-4">Upload a document</h2>
          <UploadZone />
        </div>

        <div>
          <h2 className="text-xl font-semibold text-stone-800 mb-4">Your documents</h2>

          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 bg-white border border-stone-200 rounded-xl animate-pulse" />
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
