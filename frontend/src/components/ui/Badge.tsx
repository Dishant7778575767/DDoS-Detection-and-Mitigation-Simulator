import type { HTMLAttributes, ReactNode } from "react";

export type BadgeVariant =
  | "simulation"
  | "normal"
  | "warning"
  | "critical"
  | "info"
  | "outline"
  | "stale";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  children: ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  simulation:
    "bg-cyan-500/10 text-cyan-300 border-cyan-500/30 shadow-[0_0_10px_rgba(0,229,255,0.15)]",
  normal:
    "bg-emerald-500/10 text-emerald-300 border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.15)]",
  warning:
    "bg-amber-500/10 text-amber-300 border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.15)]",
  critical:
    "bg-rose-500/15 text-rose-300 border-rose-500/30 shadow-[0_0_10px_rgba(244,63,94,0.2)]",
  info:
    "bg-sky-500/10 text-sky-300 border-sky-500/30 shadow-[0_0_10px_rgba(56,189,248,0.15)]",
  outline:
    "bg-transparent text-slate-300 border-slate-700",
  stale:
    "bg-yellow-500/10 text-yellow-400 border-yellow-500/30 animate-pulse",
};

export function Badge({
  variant = "info",
  className = "",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border uppercase tracking-wider ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}

