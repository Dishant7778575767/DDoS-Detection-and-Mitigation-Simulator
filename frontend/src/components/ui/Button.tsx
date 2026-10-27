import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "cyan" | "danger" | "outline" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  children: ReactNode;
  loading?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-[#00FF9D] hover:bg-[#26ffa9] text-[#090D16] font-bold shadow-[0_0_18px_rgba(0,255,157,0.35)] hover:shadow-[0_0_24px_rgba(0,255,157,0.55)] border border-[#00FF9D]/60",
  cyan:
    "bg-[#06B6D4] hover:bg-[#22d3ee] text-[#090D16] font-bold shadow-[0_0_18px_rgba(6,182,212,0.35)] hover:shadow-[0_0_24px_rgba(6,182,212,0.55)] border border-[#06B6D4]/60",
  danger:
    "bg-[#EF4444] hover:bg-[#f87171] text-white font-semibold shadow-[0_0_18px_rgba(239,68,68,0.35)] hover:shadow-[0_0_24px_rgba(239,68,68,0.55)] border border-red-400/40",
  outline:
    "bg-[rgba(31,41,55,0.6)] hover:bg-[rgba(31,41,55,0.9)] text-[#9CA3AF] hover:text-[#00FF9D] border border-[rgba(75,85,99,0.4)] hover:border-[#00FF9D]/40 backdrop-blur-md transition-colors",
  ghost:
    "bg-transparent hover:bg-[rgba(31,41,55,0.5)] text-[#9CA3AF] hover:text-[#F3F4F6] border border-transparent",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs rounded-md",
  md: "px-4 py-2 text-sm rounded-lg",
  lg: "px-6 py-3 text-base rounded-lg",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className = "",
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      suppressHydrationWarning
      className={`inline-flex items-center justify-center gap-2 transition-all cursor-pointer font-sans disabled:opacity-50 disabled:cursor-not-allowed ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : null}
      {children}
    </button>
  );
}
