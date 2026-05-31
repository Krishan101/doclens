import { useState } from 'react';
import type { SourceChunk } from '../../types';

interface AnswerActionsProps {
  answer: string;
  sources: SourceChunk[];
  onRegenerate: () => void;
  onFollowUp: () => void;
}

export default function AnswerActions({ answer, sources, onRegenerate, onFollowUp }: AnswerActionsProps) {
  const [copied, setCopied] = useState<'answer' | 'full' | null>(null);

  const copyAnswer = () => {
    navigator.clipboard.writeText(answer);
    setCopied('answer');
    setTimeout(() => setCopied(null), 2000);
  };

  const copyWithSources = () => {
    const text = [
      `Answer: ${answer}`,
      '',
      'Sources:',
      ...sources.map((s, i) =>
        `[${i + 1}] Page ${s.page_number ?? '?'}: ${s.content.slice(0, 150)}...`
      ),
    ].join('\n');
    navigator.clipboard.writeText(text);
    setCopied('full');
    setTimeout(() => setCopied(null), 2000);
  };

  const btn =
    'text-xs text-stone-400 hover:text-stone-600 flex items-center gap-1 px-2 py-1 rounded hover:bg-stone-100 transition-colors';

  return (
    <div className="flex items-center gap-1 pt-2 border-t border-stone-100 mt-2 flex-wrap">
      <button onClick={copyAnswer} className={btn}>
        {copied === 'answer' ? '✓ Copied' : 'Copy answer'}
      </button>
      <button onClick={copyWithSources} className={btn}>
        {copied === 'full' ? '✓ Copied' : 'Copy with sources'}
      </button>
      <button onClick={onFollowUp} className={btn}>
        Ask follow-up ↓
      </button>
      <div className="flex-1" />
      <button onClick={onRegenerate} className={btn}>
        ↺ Regenerate
      </button>
    </div>
  );
}
