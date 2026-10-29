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
    "bg-[#00FF9D] hover:bg-[#26ffa9] text-[#090D16] font-bold shadow-[0_0_18px_rgba(0,255,157,0.35)] hover:shadow-[0_0_24px_rgba(0,255,157,0.55)] border border-[#00FF9D]/60 focus-visible:ring-[#00FF9D]",
  cyan:
    "bg-[#06B6D4] hover:bg-[#22d3ee] text-[#090D16] font-bold shadow-[0_0_18px_rgba(6,182,212,0.35)] hover:shadow-[0_0_24px_rgba(6,182,212,0.55)] border border-[#06B6D4]/60 focus-visible:ring-[#06B6D4]",
  danger:
    "bg-[#EF4444] hover:bg-[#f87171] text-white font-semibold shadow-[0_0_18px_rgba(239,68,68,0.35)] hover:shadow-[0_0_24px_rgba(239,68,68,0.55)] border border-red-400/40 focus-visible:ring-[#EF4444]",
  outline:
    "bg-[#1F2937]/60 hover:bg-[#1F2937]/90 text-gray-300 hover:text-[#00FF9D] border border-gray-700/60 hover:border-[#00FF9D]/50 backdrop-blur-md focus-visible:ring-[#00FF9D]",
  ghost:
    "bg-transparent hover:bg-[#1F2937]/50 text-gray-400 hover:text-gray-100 border border-transparent focus-visible:ring-gray-400",
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
  type = "button",
  ...props
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      suppressHydrationWarning
      disabled={isDisabled}
      aria-busy={loading}
      aria-disabled={isDisabled}
      className={`inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 cursor-pointer font-sans select-none active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#090D16] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {loading && (
        <span
          className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  );
}
