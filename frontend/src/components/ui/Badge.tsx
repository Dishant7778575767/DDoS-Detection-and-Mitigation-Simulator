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
    "bg-[rgba(0,255,157,0.12)] text-[#00FF9D] border-[#00FF9D]/40 shadow-[0_0_10px_rgba(0,255,157,0.2)]",
  cyan:
    "bg-[rgba(6,182,212,0.12)] text-[#06B6D4] border-[#06B6D4]/40 shadow-[0_0_10px_rgba(6,182,212,0.2)]",
  simulation:
    "bg-[rgba(6,182,212,0.12)] text-[#06B6D4] border-[#06B6D4]/40 shadow-[0_0_10px_rgba(6,182,212,0.2)]",
  normal:
    "bg-[rgba(16,185,129,0.15)] text-[#10B981] border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.2)]",
  warning:
    "bg-[rgba(245,158,11,0.15)] text-[#F59E0B] border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.2)]",
  critical:
    "bg-[rgba(239,68,68,0.18)] text-[#EF4444] border-red-500/40 shadow-[0_0_10px_rgba(239,68,68,0.25)]",
  info:
    "bg-[rgba(6,182,212,0.12)] text-[#06B6D4] border-[#06B6D4]/40 shadow-[0_0_10px_rgba(6,182,212,0.2)]",
  outline:
    "bg-[rgba(31,41,55,0.4)] text-[#9CA3AF] border-[rgba(75,85,99,0.4)]",
  stale:
    "bg-[rgba(245,158,11,0.15)] text-[#F59E0B] border-amber-500/40 animate-pulse",
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
