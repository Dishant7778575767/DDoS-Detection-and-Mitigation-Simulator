import type { Metadata } from "next";
import Link from "next/link";

import { Sidebar } from "@/components/layout/Sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "SENTRIX | DDoS Defense Prototype",
  description: "SENTRIX defensive traffic detection prototype dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <div className="app-shell">
          <header className="app-header">
            <Link className="brand" href="/overview">
              <span className="brand-mark" aria-hidden="true">
                S
              </span>
              <span>
                <strong>SENTRIX</strong>
                <span className="brand-subtitle">Defense prototype</span>
              </span>
            </Link>
            <span className="mode-badge">SIMULATION DEFAULT</span>
          </header>
          <Sidebar />
          <main className="main-content" id="main-content" tabIndex={-1}>
            {children}
          </main>
          <footer className="app-footer">
            Planning-stage prototype · No live telemetry or network enforcement
          </footer>
        </div>
      </body>
    </html>
  );
}
