import { useState, useCallback } from 'react';
import { Upload, FileText, AlertCircle } from 'lucide-react';
import { useUploadDocument } from '../../hooks/useDocuments';

export default function UploadZone() {
  const [dragActive, setDragActive] = useState(false);
  const upload = useUploadDocument();

  const handleFile = useCallback((file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'txt'].includes(ext || '')) {
      alert('Only PDF and TXT files are supported.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      alert('File too large. Maximum 20MB.');
      return;
    }
    upload.mutate(file);
  }, [upload]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) handleFile(e.target.files[0]);
  }, [handleFile]);

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
        ${dragActive ? 'border-accent-500 bg-accent-50' : 'border-stone-300 hover:border-stone-400 bg-white'}`}
    >
      <input
        type="file"
        accept=".pdf,.txt"
        onChange={handleChange}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
      />

      {upload.isPending ? (
        <div className="flex flex-col items-center gap-2">
          <div className="w-8 h-8 border-2 border-stone-300 border-t-accent-500 rounded-full animate-spin" />
          <p className="text-sm text-stone-600">Uploading...</p>
        </div>
      ) : upload.isError ? (
        <div className="flex flex-col items-center gap-2">
          <AlertCircle className="w-8 h-8 text-red-400" />
          <p className="text-sm text-red-600">Upload failed. Try again.</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <Upload className="w-8 h-8 text-stone-400" />
          <p className="text-sm font-medium text-stone-700">Drop a file here or click to upload</p>
          <p className="text-xs text-stone-400">PDF or TXT, up to 20MB</p>
        </div>
      )}
    </div>
  );
}
