import { useParams, Navigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useDocument, useDocumentChunks } from '../hooks/useDocuments';
import { HighlightProvider } from '../context/HighlightContext';
import WorkspaceHeader from '../components/workspace/WorkspaceHeader';
import DocumentPanel from '../components/workspace/DocumentPanel';
import QueryPanel from '../components/workspace/QueryPanel';

export default function WorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const { data: doc, isLoading: docLoading } = useDocument(id);
  const { data: chunksData, isLoading: chunksLoading } = useDocumentChunks(
    id,
    doc?.status === 'ready'
  );

  if (!id) return <Navigate to="/" replace />;

  if (docLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-stone-50">
        <Loader2 className="w-8 h-8 text-stone-400 animate-spin" />
      </div>
    );
  }

  if (!doc) return <Navigate to="/" replace />;

  // Still processing
  if (doc.status === 'processing') {
    return (
      <div className="min-h-screen bg-stone-50">
        <HighlightProvider>
          <WorkspaceHeader doc={doc} />
          <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 53px)' }}>
            <div className="text-center space-y-3">
              <Loader2 className="w-10 h-10 text-accent-500 animate-spin mx-auto" />
              <p className="text-sm font-medium text-stone-700">Processing document...</p>
              <p className="text-xs text-stone-500">Extracting text, generating embeddings</p>
            </div>
          </div>
        </HighlightProvider>
      </div>
    );
  }

  // Failed or empty
  if (doc.status === 'failed' || doc.status === 'empty') {
    return (
      <div className="min-h-screen bg-stone-50">
        <HighlightProvider>
          <WorkspaceHeader doc={doc} />
          <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 53px)' }}>
            <div className="text-center space-y-3 max-w-md px-4">
              <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto">
                <span className="text-red-500 text-lg">!</span>
              </div>
              <p className="text-sm font-medium text-stone-700">
                {doc.status === 'failed' ? 'Processing failed' : 'Document is empty'}
              </p>
              <p className="text-xs text-stone-500">{doc.error_msg || 'No content could be extracted.'}</p>
            </div>
          </div>
        </HighlightProvider>
      </div>
    );
  }

  // Ready — show workspace
  return (
    <HighlightProvider>
      <div className="min-h-screen bg-stone-50 flex flex-col">
        <WorkspaceHeader doc={doc} />

        <div className="flex-1 flex flex-col lg:flex-row" style={{ height: 'calc(100vh - 53px)' }}>
          {/* Document View — 65% */}
          <div className="flex-1 lg:w-[65%] overflow-hidden">
            <DocumentPanel chunks={chunksData?.chunks} isLoading={chunksLoading} />
          </div>

          {/* Query Panel — 35% */}
          <div className="lg:w-[35%] h-[50vh] lg:h-full">
            <QueryPanel documentId={id} />
          </div>
        </div>
      </div>
    </HighlightProvider>
  );
}
