interface ThreatGaugeProps {
  score: number;
  cutoff?: number;
  label?: string;
}

export function ThreatGauge({ score, cutoff = 0.75, label }: ThreatGaugeProps) {
  const percentage = Math.round(score * 100);
  const isThreat = score >= cutoff;

  return (
    <div className="space-y-1.5 font-mono text-xs">
      <div className="flex justify-between items-center">
        <span className="text-sky-300/70">{label || "ML Threat Probability"}</span>
        <span className={`font-bold ${isThreat ? "text-rose-400" : "text-emerald-400"}`}>
          {percentage}% {isThreat ? "(THREAT)" : "(BENIGN)"}
        </span>
      </div>
      <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden relative">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isThreat
              ? "bg-linear-to-r from-amber-500 to-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]"
              : "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]"
          }`}
          style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
        />
        {/* Cutoff Marker Line */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-yellow-400 z-10"
          style={{ left: `${cutoff * 100}%` }}
          title={`Cutoff: ${(cutoff * 100).toFixed(0)}%`}
        />
      </div>
      <div className="flex justify-between text-[10px] text-sky-200/40">
        <span>0%</span>
        <span>Cutoff: {(cutoff * 100).toFixed(0)}%</span>
        <span>100%</span>
      </div>
    </div>
  );
}

