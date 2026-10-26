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
    <Card className={className}>
      <CardHeader className="mb-2 pb-2">
        <CardTitle className="text-sm font-medium text-sky-300/80">
          {title}
        </CardTitle>
        <div className="text-cyan-400">{icon}</div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="text-2xl font-mono font-bold text-cyan-50">
            {typeof value === "number" ? value.toLocaleString() : value}{" "}
            {unit && <span className="text-xs text-sky-300/50 font-normal">{unit}</span>}
          </div>
          {badge}
        </div>
        {subtitle && (
          <p className="text-xs text-sky-200/50 mt-1">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

