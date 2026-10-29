"use client";

import { Badge } from "@/components/ui/Badge";
import { RotateCcw } from "@/components/ui/icons";
import type { SimulationRunSummary } from "@/types";

interface SimulatorHistoryTableProps {
  pastRuns: SimulationRunSummary[];
  activeRunId?: string;
  onRefresh: () => void;
  onLoadRun: (runId: string) => void;
}

export function SimulatorHistoryTable({
  pastRuns,
  activeRunId,
  onRefresh,
  onLoadRun,
}: SimulatorHistoryTableProps) {
  return (
    <div className="bg-[#111827]/70 backdrop-blur-xl border border-gray-700/60 rounded-xl p-5 shadow-xl space-y-3 font-mono">
      <div className="flex items-center justify-between border-b border-gray-800 pb-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-200 flex items-center gap-2">
          <RotateCcw className="w-3.5 h-3.5 text-[#00FF9D]" />
          Previous Chaos Replay Sessions
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          className="text-[11px] font-mono text-[#00FF9D] hover:underline cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00FF9D] rounded px-1"
        >
          Refresh List
        </button>
      </div>

      {pastRuns.length === 0 ? (
        <span className="text-xs text-gray-400 font-mono">No simulation runs recorded yet.</span>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-700/60 bg-[#090D16]">
          <table className="w-full text-left text-xs font-mono" aria-label="Previous Simulation Runs">
            <thead>
              <tr className="text-gray-400 border-b border-gray-800 bg-[#1F2937]/50 text-[11px] uppercase">
                <th scope="col" className="py-2.5 px-3">Run ID</th>
                <th scope="col" className="py-2.5 px-3">Scenario</th>
                <th scope="col" className="py-2.5 px-3">Status</th>
                <th scope="col" className="py-2.5 px-3">Progress</th>
                <th scope="col" className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/80">
              {pastRuns.map((r) => (
                <tr
                  key={r.run_id}
                  className={`hover:bg-[#1F2937]/40 transition-colors ${
                    activeRunId === r.run_id ? "bg-[rgba(0,255,157,0.08)]" : ""
                  }`}
                >
                  <td className="py-2.5 px-3 text-[#00FF9D] font-bold">{r.run_id}</td>
                  <td className="py-2.5 px-3 text-gray-200">{r.scenario_type}</td>
                  <td className="py-2.5 px-3">
                    <Badge
                      variant={
                        r.status === "completed"
                          ? "normal"
                          : r.status === "running"
                          ? "critical"
                          : r.status === "paused"
                          ? "warning"
                          : "outline"
                      }
                      className="text-[10px]"
                    >
                      {r.status}
                    </Badge>
                  </td>
                  <td className="py-2.5 px-3 text-gray-400">
                    {r.current_tick} / {r.total_ticks}s
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    <button
                      type="button"
                      onClick={() => onLoadRun(r.run_id)}
                      className="text-[#00FF9D] hover:underline font-semibold cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00FF9D] rounded px-1"
                    >
                      Load Session
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

