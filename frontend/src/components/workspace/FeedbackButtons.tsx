import { useState } from 'react';
import { ThumbsUp, ThumbsDown } from 'lucide-react';
import api from '../../api/client';

interface FeedbackButtonsProps {
  queryId: string;
}

export default function FeedbackButtons({ queryId }: FeedbackButtonsProps) {
  const [submitted, setSubmitted] = useState<'up' | 'down' | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (rating: 'up' | 'down') => {
    if (submitted || loading) return;
    setLoading(true);
    try {
      await api.post('/feedback', { query_id: queryId, rating });
      setSubmitted(rating);
    } catch (err: any) {
      if (err.response?.status === 409) {
        setSubmitted(rating); // already submitted
      }
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-stone-400">
        {submitted === 'up' ? (
          <><ThumbsUp className="w-3.5 h-3.5 text-green-500 fill-green-500" /> Thanks for the feedback</>
        ) : (
          <><ThumbsDown className="w-3.5 h-3.5 text-red-400 fill-red-400" /> We'll work on improving</>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 text-xs text-stone-400">
      <span>Was this helpful?</span>
      <button
        onClick={() => submit('up')}
        disabled={loading}
        className="p-1 rounded hover:bg-green-50 hover:text-green-600 transition-colors"
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={() => submit('down')}
        disabled={loading}
        className="p-1 rounded hover:bg-red-50 hover:text-red-500 transition-colors"
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
