import { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {icon && <div className="text-stone-300 mb-4">{icon}</div>}
      <h3 className="text-lg font-medium text-stone-700 mb-2">{title}</h3>
      {description && <p className="text-sm text-stone-500 max-w-md mb-6">{description}</p>}
      {action}
    </div>
  );
}
