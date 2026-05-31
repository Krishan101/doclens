import { useState, forwardRef, useImperativeHandle, useRef } from 'react';
import { Send, Loader2 } from 'lucide-react';

interface QueryInputProps {
  onSubmit: (question: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export interface QueryInputRef {
  focus: () => void;
  setValue: (v: string) => void;
}

const QueryInput = forwardRef<QueryInputRef, QueryInputProps>(
  ({ onSubmit, isLoading, disabled }, ref) => {
    const [question, setQuestion] = useState('');
    const inputRef = useRef<HTMLInputElement>(null);

    useImperativeHandle(ref, () => ({
      focus: () => inputRef.current?.focus(),
      setValue: (v: string) => setQuestion(v),
    }));

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      if (!question.trim() || isLoading || disabled) return;
      onSubmit(question.trim());
      setQuestion('');
    };

    return (
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this document..."
          disabled={isLoading || disabled}
          className="flex-1 px-3 py-2.5 border border-stone-300 rounded-lg text-sm
            focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-transparent
            disabled:opacity-50 disabled:cursor-not-allowed bg-white"
        />
        <button
          type="submit"
          disabled={!question.trim() || isLoading || disabled}
          className="px-4 py-2.5 bg-stone-900 text-white rounded-lg hover:bg-stone-800
            disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </form>
    );
  }
);

QueryInput.displayName = 'QueryInput';
export default QueryInput;
