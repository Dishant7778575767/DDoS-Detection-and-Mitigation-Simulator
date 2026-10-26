interface StatusIndicatorProps {
  status: "online" | "stale" | "disconnected" | "loading";
  label?: string;
  className?: string;
}

export function StatusIndicator({
  status,
  label,
  className = "",
}: StatusIndicatorProps) {
  const dotStyles: Record<string, string> = {
    online: "bg-emerald-400 shadow-[0_0_8px_#34d399]",
    stale: "bg-amber-400 shadow-[0_0_8px_#fbbf24] animate-pulse",
    disconnected: "bg-rose-500 shadow-[0_0_8px_#f43f5e]",
    loading: "bg-sky-400 shadow-[0_0_8px_#38bdf8] animate-ping",
  };

  const defaultLabels: Record<string, string> = {
    online: "Live Feed Active",
    stale: "Data Stale",
    disconnected: "Backend Disconnected",
    loading: "Syncing...",
  };

  return (
    <div className={`inline-flex items-center gap-2 text-xs font-mono tracking-wider ${className}`}>
      <span className="relative flex h-2.5 w-2.5">
        <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${dotStyles[status]}`} />
      </span>
      <span className="text-sky-200/80">{label || defaultLabels[status]}</span>
    </div>
  );
}

