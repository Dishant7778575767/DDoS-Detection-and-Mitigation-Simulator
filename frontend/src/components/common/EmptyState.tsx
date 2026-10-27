import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center rounded-xl border border-dashed border-[rgba(75,85,99,0.4)] bg-[#090D16]/60 backdrop-blur-md my-4 font-mono">
      {icon && <div className="text-[#00FF9D]/60 mb-3">{icon}</div>}
      <h4 className="text-sm font-semibold text-gray-100">{title}</h4>
      {description && (
        <p className="text-xs text-[#9CA3AF] mt-1 max-w-sm font-sans">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
