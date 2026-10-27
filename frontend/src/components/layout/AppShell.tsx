"use client";

import { useCallback, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bell,
  History as HistoryIcon,
  Menu,
  Shield,
  Sliders,
  XCircle,
  Zap,
} from "@/components/ui/icons";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/polling";

const routes = [
  {
    href: "/overview",
    label: "Overview",
    sublabel: "Live Traffic & AI Status",
    icon: Activity,
  },
  {
    href: "/simulator",
    label: "Simulator",
    sublabel: "Attack vs Safe Traffic",
    icon: Zap,
    badge: "Live",
  },
  {
    href: "/alerts",
    label: "Threat Incidents",
    sublabel: "Detected Attacks List",
    icon: Bell,
  },
  {
    href: "/mitigation",
    label: "Defense Shield",
    sublabel: "Active Blocking Rules",
    icon: Shield,
  },
  {
    href: "/history",
    label: "Audit Trail",
    sublabel: "Past Security Log",
    icon: HistoryIcon,
  },
  {
    href: "/settings",
    label: "Configuration",
    sublabel: "AI Sensitivity Settings",
    icon: Sliders,
  },
];

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const fetchStatus = useCallback(() => api.getMitigationStatus(), []);
  const { data: shieldStatus } = usePolling(fetchStatus, 3000);

  const isShieldActive = Boolean(shieldStatus?.shield_active);
  const remainingSec = shieldStatus?.latest_mitigation?.remaining_seconds ?? 0;

  return (
    <div className="app-shell">
      {/* Top DevSecOps Header */}
      <header className="app-header">
        <div className="flex items-center gap-3">
          <button
            suppressHydrationWarning
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden p-2 rounded-lg bg-[#1F2937]/60 border border-[rgba(75,85,99,0.4)] text-[#9CA3AF] hover:text-[#00FF9D] transition-colors"
            aria-label="Toggle Navigation Drawer"
          >
            <Menu className="w-5 h-5" />
          </button>

          <Link className="brand" href="/overview">
            <span className="brand-mark shadow-[0_0_15px_rgba(0,255,157,0.3)]" aria-hidden="true">
              S
            </span>
            <div className="flex flex-col">
              <span className="text-gray-100 font-bold tracking-widest text-lg font-mono flex items-center gap-2">
                SENTRIX
              </span>
              <span className="text-[11px] text-[#9CA3AF] font-mono leading-none">
                DDos Detection & Mitigation Simulator
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {/* Synchronized Defense Shield Global Pill */}
          <Link
            href="/mitigation"
            className={`hidden sm:inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono transition-all border ${
              isShieldActive
                ? "bg-[rgba(0,255,157,0.15)] border-[#00FF9D]/50 text-[#00FF9D] shadow-[0_0_12px_rgba(0,255,157,0.3)]"
                : "bg-[#1F2937]/60 border-[rgba(75,85,99,0.4)] text-gray-300 hover:text-white"
            }`}
          >
            <Shield className={`w-3.5 h-3.5 ${isShieldActive ? "text-[#00FF9D] animate-pulse" : "text-[#06B6D4]"}`} />
            <span className="font-bold">
              {isShieldActive ? `SHIELD: ACTIVE (${remainingSec}s)` : "SHIELD: STANDBY"}
            </span>
          </Link>

          {/* Zero Impact Mode badge */}
          <span className="mode-badge hidden xl:inline-flex">
            <span className="inline-block w-2 h-2 rounded-full bg-[#06B6D4] animate-pulse" />
            SIMULATION MODE (ZERO IMPACT)
          </span>
        </div>
      </header>

      {/* Desktop Sidebar */}
      <nav aria-label="Main navigation" className="sidebar hidden lg:flex">
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
                className={`sidebar-link flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl transition-all ${
                  active
                    ? "bg-[#00FF9D]/10 border-l-2 border-l-[#00FF9D] border-y border-r border-[#00FF9D]/30 text-[#00FF9D] shadow-[0_0_20px_rgba(0,255,157,0.15)]"
                    : "text-[#9CA3AF] hover:bg-[#1F2937]/60 hover:text-gray-100 border border-transparent"
                }`}
                href={route.href}
                key={route.href}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 shrink-0 ${active ? "text-[#00FF9D]" : "text-[#9CA3AF]"}`} />
                  <div className="flex flex-col text-left">
                    <span className="text-xs font-semibold leading-tight font-sans">{route.label}</span>
                    <span className="text-[10px] text-[#9CA3AF]/60 font-mono leading-tight">
                      {route.sublabel}
                    </span>
                  </div>
                </div>

                {route.badge && (
                  <span className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded font-bold border ${
                    route.badge === "Live"
                      ? "bg-[#00FF9D]/15 text-[#00FF9D] border-[#00FF9D]/40"
                      : "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/40"
                  }`}>
                    {route.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Mobile Sidebar Overlay Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative w-72 max-w-[85vw] bg-[#090D16] border-r border-[rgba(75,85,99,0.4)] p-4 flex flex-col z-10 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-[rgba(75,85,99,0.3)] mb-4">
              <span className="font-mono text-sm font-bold text-gray-100 flex items-center gap-2">
                <span className="brand-mark w-7 h-7 text-xs">S</span>
                SENTRIX
              </span>
              <button
                onClick={() => setMobileOpen(false)}
                className="text-[#9CA3AF] hover:text-white"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-1 overflow-y-auto">
              {routes.map((route) => {
                const active = pathname === route.href;
                const Icon = route.icon;
                return (
                  <Link
                    key={route.href}
                    href={route.href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl transition-all ${
                      active
                        ? "bg-[#00FF9D]/15 border border-[#00FF9D]/40 text-[#00FF9D]"
                        : "text-[#9CA3AF] hover:bg-[#1F2937]/60 hover:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="w-4 h-4 shrink-0" />
                      <div className="flex flex-col text-left">
                        <span className="text-xs font-semibold">{route.label}</span>
                        <span className="text-[10px] text-[#9CA3AF]/60 font-mono">{route.sublabel}</span>
                      </div>
                    </div>
                    {route.badge && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#00FF9D]/20 text-[#00FF9D] border border-[#00FF9D]/40">
                        {route.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Main Content Pane */}
      <main className="main-content" id="main-content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
