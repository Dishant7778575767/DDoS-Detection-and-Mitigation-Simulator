"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bell,
  History as HistoryIcon,
  Shield,
  Sliders,
  Zap,
} from "@/components/ui/icons";

const routes = [
  {
    href: "/overview",
    label: "Overview",
    sublabel: "Live Telemetry",
    icon: Activity,
  },
  {
    href: "/simulator",
    label: "Simulator",
    sublabel: "Chaos & Replay",
    icon: Zap,
    badge: "Live",
  },
  {
    href: "/alerts",
    label: "Threat Incidents",
    sublabel: "CVEs & Anomalies",
    icon: Bell,
  },
  {
    href: "/mitigation",
    label: "Protection",
    sublabel: "eBPF & Safety Gate",
    icon: Shield,
  },
  {
    href: "/history",
    label: "Audit Trail",
    sublabel: "Immutable Ledger",
    icon: HistoryIcon,
  },
  {
    href: "/settings",
    label: "Configuration",
    sublabel: "Detection Bounds",
    icon: Sliders,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav aria-label="Main navigation" className="sidebar">
      <div className="text-[10px] uppercase tracking-wider text-[#9CA3AF] font-mono px-3 mb-2 flex items-center justify-between">
        <span>Control Plane</span>
        <span className="w-1.5 h-1.5 rounded-full bg-[#00FF9D] shadow-[0_0_8px_#00FF9D] animate-pulse" />
      </div>
      <div className="space-y-1">
        {routes.map((route) => {
          const active = pathname === route.href;
          const Icon = route.icon;
          return (
            <Link
              aria-current={active ? "page" : undefined}
              className={`sidebar-link flex items-center justify-between gap-3 px-3 py-2 rounded-xl transition-all ${
                active
                  ? "bg-[#00FF9D]/10 border-l-2 border-l-[#00FF9D] border-y border-r border-[#00FF9D]/30 text-[#00FF9D] shadow-[0_0_15px_rgba(0,255,157,0.15)]"
                  : "text-[#9CA3AF] hover:bg-[#1F2937]/60 hover:text-gray-100"
              }`}
              href={route.href}
              key={route.href}
            >
              <div className="flex items-center gap-3">
                <Icon className={`w-4 h-4 shrink-0 ${active ? "text-[#00FF9D]" : "text-[#9CA3AF]"}`} />
                <div className="flex flex-col text-left">
                  <span className="text-xs font-semibold leading-tight">{route.label}</span>
                  <span className="text-[10px] text-[#9CA3AF]/60 font-mono leading-tight">
                    {route.sublabel}
                  </span>
                </div>
              </div>

              {route.badge && (
                <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded font-bold border ${
                  route.badge === "Live"
                    ? "bg-[#00FF9D]/20 text-[#00FF9D] border-[#00FF9D]/40"
                    : "bg-[#06B6D4]/20 text-[#06B6D4] border-[#06B6D4]/40"
                }`}>
                  {route.badge}
                </span>
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
