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
    online: "bg-[#10B981] shadow-[0_0_10px_#10B981]",
    stale: "bg-[#F59E0B] shadow-[0_0_10px_#F59E0B] animate-pulse",
    disconnected: "bg-[#EF4444] shadow-[0_0_10px_#EF4444]",
    loading: "bg-[#06B6D4] shadow-[0_0_10px_#06B6D4] animate-ping",
  };

  const defaultLabels: Record<string, string> = {
    online: "Simulator: Online",
    stale: "Data Stale",
    disconnected: "Control Plane Offline",
    loading: "Loading Data...",
  };

  return (
    <div className={`inline-flex items-center gap-2 text-xs font-mono tracking-wider ${className}`}>
      <span className="relative flex h-2.5 w-2.5">
        <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${dotStyles[status]}`} />
      </span>
      <span className="text-[#9CA3AF]">{label || defaultLabels[status]}</span>
    </div>
  );
}
