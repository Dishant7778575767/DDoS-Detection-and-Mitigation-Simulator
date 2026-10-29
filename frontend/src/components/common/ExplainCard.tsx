"use client";

import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, HelpCircle, Terminal } from "@/components/ui/icons";

interface ExplainCardProps {
  title?: string;
  summary: string;
  tips?: string[];
  technicalDetails?: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}

export function ExplainCard({
  title = "What does this mean?",
  summary,
  tips,
  technicalDetails,
  defaultOpen = false,
  className = "",
}: ExplainCardProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div
      className={`rounded-xl border border-gray-700/60 bg-[#111827]/70 p-4 transition-all ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded-lg bg-[#06B6D4]/15 p-1.5 text-[#06B6D4]">
            <HelpCircle className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-gray-200">{title}</h4>
            <p className="mt-1 text-xs text-gray-300 leading-relaxed">{summary}</p>
            {tips && tips.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs text-gray-400">
                {tips.map((tip, idx) => (
                  <li key={idx} className="flex items-center gap-1.5">
                    <span className="h-1 w-1 rounded-full bg-[#00FF9D]" />
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {technicalDetails && (
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="flex shrink-0 items-center gap-1 rounded-lg border border-gray-700/60 bg-[#1F2937]/60 px-2.5 py-1 text-[11px] font-mono text-gray-300 hover:border-[#00FF9D]/40 hover:text-[#00FF9D] transition-colors"
            aria-expanded={isOpen}
          >
            <Terminal className="h-3.5 w-3.5" />
            <span>{isOpen ? "Hide Tech Details" : "Tech Details"}</span>
            {isOpen ? (
              <ChevronUp className="h-3 w-3" />
            ) : (
              <ChevronDown className="h-3 w-3" />
            )}
          </button>
        )}
      </div>

      {isOpen && technicalDetails && (
        <div className="mt-4 rounded-lg border border-gray-800 bg-[#090D16]/90 p-3 text-xs font-mono text-gray-300">
          <div className="mb-2 flex items-center justify-between border-b border-gray-800 pb-1.5 text-[10px] text-gray-400 uppercase tracking-wider">
            <span>Developer / Technical Diagnostics</span>
            <span className="text-[#00FF9D]">Verified Telemetry</span>
          </div>
          {technicalDetails}
        </div>
      )}
    </div>
  );
}

