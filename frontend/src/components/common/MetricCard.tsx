import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  icon: ReactNode;
  badge?: ReactNode;
  className?: string;
}

export function MetricCard({
  title,
  value,
  unit,
  subtitle,
  icon,
  badge,
  className = "",
}: MetricCardProps) {
  return (
    <Card className={`group relative overflow-hidden transition-all duration-200 hover:border-[#00FF9D]/40 hover:shadow-[0_0_25px_rgba(0,255,157,0.12)] ${className}`}>
      <div className="absolute top-0 left-0 right-0 h-0.5 bg-linear-to-r from-transparent via-[#00FF9D]/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      <CardHeader className="mb-2 pb-2">
        <CardTitle className="text-xs font-mono uppercase tracking-wider text-gray-400">
          {title}
        </CardTitle>
        <div className="text-[#00FF9D] group-hover:scale-110 transition-transform">
          {icon}
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline justify-between gap-2">
          <div className="text-2xl font-mono font-bold tracking-tight text-white">
            {typeof value === "number" ? value.toLocaleString() : value}{" "}
            {unit && <span className="text-xs text-gray-400 font-normal">{unit}</span>}
          </div>
          {badge}
        </div>
        {subtitle && (
          <p className="text-[11px] font-mono text-gray-400 mt-1 leading-snug">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}
