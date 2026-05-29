const config = {
  high: { dot: 'bg-green-500', text: 'text-green-700', bg: 'bg-green-50', label: 'High confidence' },
  low: { dot: 'bg-amber-500', text: 'text-amber-700', bg: 'bg-amber-50', label: 'Low confidence' },
  none: { dot: 'bg-stone-400', text: 'text-stone-600', bg: 'bg-stone-100', label: 'No match found' },
};

export default function ConfidenceBadge({ confidence }: { confidence: 'high' | 'low' | 'none' }) {
  const c = config[confidence];
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full ${c.bg} ${c.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
      {c.label}
    </span>
  );
}
