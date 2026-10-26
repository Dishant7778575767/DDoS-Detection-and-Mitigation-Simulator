import type { Metadata } from "next";
import Link from "next/link";

import { Sidebar } from "@/components/layout/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "SENTRIX | Defensive DDoS Platform",
  description: "SENTRIX AI-powered defensive DDoS detection and mitigation control plane",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-[#050b14] text-[#f0f6fc] antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <div className="app-shell">
          <header className="app-header">
            <Link className="brand" href="/overview">
              <span className="brand-mark shadow-[0_0_15px_rgba(0,229,255,0.3)]" aria-hidden="true">
                S
              </span>
              <span>
                <strong className="text-cyan-50 font-bold tracking-widest text-lg">SENTRIX</strong>
                <span className="brand-subtitle text-xs text-sky-300/60 font-mono">DDoS Defense Platform</span>
              </span>
            </Link>
            <div className="flex items-center gap-3">
              <span className="mode-badge">
                <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                SIMULATION MODE ACTIVE (ZERO NETWORK IMPACT)
              </span>
            </div>
          </header>
          <Sidebar />
          <main className="main-content" id="main-content" tabIndex={-1}>
            {children}
          </main>
          <footer className="app-footer">
            <span>SENTRIX Defensive DDoS Control Plane</span>
            <span>·</span>
            <span>Default Simulation Mode</span>
            <span>·</span>
            <span>Fail-Closed Safety Gate Enabled</span>
          </footer>
        </div>
      </body>
    </html>
  );
}
