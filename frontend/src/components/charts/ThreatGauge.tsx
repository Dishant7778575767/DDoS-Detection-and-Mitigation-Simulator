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
        <span className="text-[#9CA3AF]">{label || "RandomForest ML Threat Score"}</span>
        <span className={`font-bold ${isThreat ? "text-[#EF4444]" : "text-[#00FF9D]"}`}>
          {percentage}% {isThreat ? "[THREAT DETECTED]" : "[BENIGN FLOW]"}
        </span>
      </div>
      <div className="w-full h-2 rounded-full bg-[#1F2937] overflow-hidden relative border border-[rgba(75,85,99,0.3)]">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isThreat
              ? "bg-gradient-to-r from-[#F59E0B] to-[#EF4444] shadow-[0_0_12px_rgba(239,68,68,0.6)]"
              : "bg-[#00FF9D] shadow-[0_0_12px_rgba(0,255,157,0.5)]"
          }`}
          style={{ width: `${Math.min(100, Math.max(0, percentage))}%` }}
        />
        {/* Cutoff Marker Line */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-[#06B6D4] z-10 shadow-[0_0_6px_#06B6D4]"
          style={{ left: `${cutoff * 100}%` }}
          title={`Policy Gate Cutoff: ${(cutoff * 100).toFixed(0)}%`}
        />
      </div>
      <div className="flex justify-between text-[10px] text-[#9CA3AF]/60 font-mono">
        <span>0%</span>
        <span className="text-[#06B6D4]">Gate Cutoff: {(cutoff * 100).toFixed(0)}%</span>
        <span>100%</span>
      </div>
    </div>
  );
}
