import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-xl border border-dashed border-cyan-500/20 bg-slate-950/40 my-4">
      {icon && <div className="text-sky-400/60 mb-3">{icon}</div>}
      <h4 className="text-sm font-semibold text-cyan-100">{title}</h4>
      {description && (
        <p className="text-xs text-sky-200/50 mt-1 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

