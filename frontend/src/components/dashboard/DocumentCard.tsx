import { useNavigate } from 'react-router-dom';
import { FileText, Loader2, AlertCircle, Trash2, CheckCircle2 } from 'lucide-react';
import type { Document } from '../../types';
import { useDeleteDocument } from '../../hooks/useDocuments';

const statusConfig = {
  processing: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-50', label: 'Processing...', spin: true },
  ready: { icon: CheckCircle2, color: 'text-green-600', bg: 'bg-green-50', label: 'Ready', spin: false },
  failed: { icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-50', label: 'Failed', spin: false },
  empty: { icon: AlertCircle, color: 'text-amber-500', bg: 'bg-amber-50', label: 'Empty', spin: false },
};

export default function DocumentCard({ doc }: { doc: Document }) {
  const navigate = useNavigate();
  const deleteDoc = useDeleteDocument();
  const status = statusConfig[doc.status];
  const StatusIcon = status.icon;

  const handleClick = () => {
    if (doc.status === 'ready') navigate(`/doc/${doc.id}`);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this document and all its data?')) {
      deleteDoc.mutate(doc.id);
    }
  };

  const fileSize = doc.file_size < 1024 * 1024
    ? `${(doc.file_size / 1024).toFixed(0)} KB`
    : `${(doc.file_size / (1024 * 1024)).toFixed(1)} MB`;

  return (
    <div
      onClick={handleClick}
      className={`group bg-white border border-stone-200 rounded-xl p-4 transition-all
        ${doc.status === 'ready' ? 'cursor-pointer hover:border-stone-300 hover:shadow-sm' : ''}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3 min-w-0">
          <FileText className="w-5 h-5 text-stone-400 mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-stone-800 truncate">{doc.filename}</p>
            <div className="flex items-center gap-2 mt-1">
              <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${status.bg} ${status.color}`}>
                <StatusIcon className={`w-3 h-3 ${status.spin ? 'animate-spin' : ''}`} />
                {status.label}
              </span>
              <span className="text-xs text-stone-400">{fileSize}</span>
              {doc.chunk_count != null && (
                <span className="text-xs text-stone-400">{doc.chunk_count} chunks</span>
              )}
            </div>
            {doc.error_msg && (
              <p className="text-xs text-red-500 mt-1 line-clamp-2">{doc.error_msg}</p>
            )}
          </div>
        </div>

        <button
          onClick={handleDelete}
          className="opacity-0 group-hover:opacity-100 p-1.5 text-stone-400 hover:text-red-500 rounded-lg hover:bg-stone-50 transition-all"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
