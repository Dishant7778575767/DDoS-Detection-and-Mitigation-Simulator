import type { HTMLAttributes, ReactNode } from "react";

export type BadgeVariant =
  | "matrix"
  | "cyan"
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
  matrix:
    "bg-[rgba(0,255,157,0.14)] text-[#00FF9D] border-[#00FF9D]/50 shadow-[0_0_10px_rgba(0,255,157,0.25)]",
  cyan:
    "bg-[rgba(6,182,212,0.14)] text-[#06B6D4] border-[#06B6D4]/50 shadow-[0_0_10px_rgba(6,182,212,0.25)]",
  simulation:
    "bg-[rgba(6,182,212,0.14)] text-[#06B6D4] border-[#06B6D4]/50 shadow-[0_0_10px_rgba(6,182,212,0.25)]",
  normal:
    "bg-emerald-500/15 text-emerald-400 border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.2)]",
  warning:
    "bg-amber-500/15 text-amber-400 border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.2)]",
  critical:
    "bg-rose-500/20 text-rose-300 border-rose-500/50 shadow-[0_0_10px_rgba(239,68,68,0.25)]",
  info:
    "bg-[rgba(6,182,212,0.14)] text-[#06B6D4] border-[#06B6D4]/50 shadow-[0_0_10px_rgba(6,182,212,0.2)]",
  outline:
    "bg-[#1F2937]/50 text-gray-300 border-gray-700/60",
  stale:
    "bg-amber-500/15 text-amber-300 border-amber-500/40 animate-pulse",
};

export function Badge({
  variant = "info",
  className = "",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-mono font-medium border uppercase tracking-wider ${variantStyles[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
