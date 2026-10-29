"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Menu,
  Shield,
  XCircle,
} from "@/components/ui/icons";
import { NAV_ROUTES } from "@/config/navigation";
import { api } from "@/lib/api";
import { usePolling } from "@/lib/polling";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const fetchStatus = useCallback(() => api.getMitigationStatus(), []);
  const { data: shieldStatus, refresh: refreshShield } = usePolling(fetchStatus, 3000);

  useEffect(() => {
    const handleShieldUpdate = () => {
      void refreshShield();
    };
    window.addEventListener("sentrix:shield_update", handleShieldUpdate);
    return () => window.removeEventListener("sentrix:shield_update", handleShieldUpdate);
  }, [refreshShield]);

  // Lock body scroll and listen for Escape when mobile drawer is active
  useEffect(() => {
    if (!mobileOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMobileOpen(false);
    };
    document.addEventListener("keydown", handleKeyDown);
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = originalOverflow;
    };
  }, [mobileOpen]);

  const isShieldActive = Boolean(shieldStatus?.shield_active);
  const remainingSec = shieldStatus?.latest_mitigation?.remaining_seconds ?? 0;

  return (
    <div className="app-shell">
      {/* Top DevSecOps Header */}
      <header className="app-header" role="banner">
        <div className="flex items-center gap-3">
          <button
            type="button"
            suppressHydrationWarning
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden p-2 rounded-lg bg-[#1F2937]/70 border border-gray-700/60 text-gray-400 hover:text-[#00FF9D] hover:border-[#00FF9D]/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00FF9D] transition-colors"
            aria-label="Toggle Navigation Drawer"
            aria-expanded={mobileOpen}
            aria-controls="mobile-navigation-drawer"
          >
            <Menu className="w-5 h-5" />
          </button>

          <Link className="brand group" href="/overview">
            <span
              className="brand-mark group-hover:shadow-[0_0_20px_rgba(0,255,157,0.45)] transition-shadow"
              aria-hidden="true"
            >
              S
            </span>
            <div className="flex flex-col">
              <span className="text-gray-100 font-bold tracking-widest text-lg font-mono flex items-center gap-2">
                SENTRIX
              </span>
              <span className="text-[11px] text-gray-400 font-mono leading-none">
                Intelligent DDoS Detection & Defense Platform
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-3">
          {/* Synchronized Defense Shield Global Pill */}
          <Link
            href="/mitigation"
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono transition-all border ${
              isShieldActive
                ? "bg-[rgba(0,255,157,0.15)] border-[#00FF9D]/60 text-[#00FF9D] shadow-[0_0_14px_rgba(0,255,157,0.35)]"
                : "bg-[#1F2937]/70 border-gray-700/60 text-gray-300 hover:text-white hover:border-gray-600"
            }`}
          >
            <Shield className={`w-3.5 h-3.5 ${isShieldActive ? "text-[#00FF9D] animate-pulse" : "text-[#06B6D4]"}`} />
            <span className="font-bold">
              {isShieldActive ? `SHIELD: ACTIVE (${remainingSec}s)` : "SHIELD: STANDBY"}
            </span>
          </Link>

          {/* Operational status badge */}
          <span className="mode-badge hidden md:inline-flex">
            <span className="inline-block w-2 h-2 rounded-full bg-[#00FF9D] animate-pulse shadow-[0_0_8px_#00FF9D]" />
            DEFENSE ENGINE ARMED
          </span>
        </div>
      </header>

      {/* Desktop Sidebar */}
      <nav aria-label="Main navigation" className="sidebar hidden lg:flex">
        <div className="text-[10px] uppercase tracking-wider text-gray-400 font-mono px-3 mb-2 flex items-center justify-between">
          <span>Control Plane</span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#00FF9D] shadow-[0_0_8px_#00FF9D] animate-pulse" />
        </div>
        <div className="space-y-1">
          {NAV_ROUTES.map((route) => {
            const active = pathname === route.href;
            const Icon = route.icon;
            return (
              <Link
                aria-current={active ? "page" : undefined}
                className={`sidebar-link flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl transition-all ${
                  active
                    ? "bg-[#00FF9D]/10 border-l-2 border-l-[#00FF9D] border-y border-r border-[#00FF9D]/30 text-[#00FF9D] shadow-[0_0_20px_rgba(0,255,157,0.15)]"
                    : "text-gray-400 hover:bg-[#1F2937]/60 hover:text-gray-100 border border-transparent"
                }`}
                href={route.href}
                key={route.href}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 shrink-0 ${active ? "text-[#00FF9D]" : "text-gray-400"}`} />
                  <div className="flex flex-col text-left">
                    <span className="text-xs font-semibold leading-tight font-sans">{route.label}</span>
                    <span className="text-[10px] text-gray-400/80 font-mono leading-tight">
                      {route.sublabel}
                    </span>
                  </div>
                </div>

                {route.badge && (
                  <span
                    className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded font-bold border ${
                      route.badge === "Live"
                        ? "bg-[#00FF9D]/15 text-[#00FF9D] border-[#00FF9D]/40"
                        : "bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/40"
                    }`}
                  >
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
        <div
          id="mobile-navigation-drawer"
          role="dialog"
          aria-modal="true"
          aria-label="Mobile Navigation"
          className="fixed inset-0 z-50 lg:hidden flex"
        >
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div className="relative w-72 max-w-[85vw] bg-[#090D16] border-r border-gray-700/60 p-4 flex flex-col z-10 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800 mb-4">
              <span className="font-mono text-sm font-bold text-gray-100 flex items-center gap-2">
                <span className="brand-mark w-7 h-7 text-xs" aria-hidden="true">S</span>
                SENTRIX
              </span>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                className="text-gray-400 hover:text-white p-1 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00FF9D]"
                aria-label="Close navigation drawer"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <nav aria-label="Mobile Navigation Links" className="space-y-1 overflow-y-auto">
              {NAV_ROUTES.map((route) => {
                const active = pathname === route.href;
                const Icon = route.icon;
                return (
                  <Link
                    key={route.href}
                    href={route.href}
                    aria-current={active ? "page" : undefined}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl transition-all ${
                      active
                        ? "bg-[#00FF9D]/15 border border-[#00FF9D]/40 text-[#00FF9D]"
                        : "text-gray-400 hover:bg-[#1F2937]/60 hover:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="w-4 h-4 shrink-0" />
                      <div className="flex flex-col text-left">
                        <span className="text-xs font-semibold">{route.label}</span>
                        <span className="text-[10px] text-gray-400/80 font-mono">{route.sublabel}</span>
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
            </nav>
          </div>
        </div>
      )}

      {/* Main Content Pane */}
      <main
        className="main-content"
        id="main-content"
        tabIndex={-1}
        role="region"
        aria-label="SENTRIX Operational Console"
      >
        {children}
      </main>
    </div>
  );
}
