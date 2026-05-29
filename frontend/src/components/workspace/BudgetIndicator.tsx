import { useBudget } from '../../hooks/useQueries';
import { Zap } from 'lucide-react';

export default function BudgetIndicator() {
  const { data: budget, isLoading } = useBudget();

  if (isLoading || !budget) return null;

  const pct = budget.remaining_pct;
  const dotColor = pct > 50 ? 'bg-green-500' : pct > 20 ? 'bg-amber-500' : 'bg-red-500';
  const isLow = pct <= 20;

  return (
    <div className="flex items-center gap-1.5 text-xs text-stone-500" title={`${budget.total_remaining} queries remaining today`}>
      <Zap className="w-3.5 h-3.5" />
      <span className={`w-2 h-2 rounded-full ${dotColor}`} />
      <span className={isLow ? 'text-red-600 font-medium' : ''}>
        {pct}%
        {isLow && budget.active_model !== budget.primary_model && ' · fallback model'}
      </span>
    </div>
  );
}
