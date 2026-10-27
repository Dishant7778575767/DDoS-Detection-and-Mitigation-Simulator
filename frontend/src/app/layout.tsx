import type { Metadata } from "next";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "SENTRIX | Cloud-Native DevSecOps DDoS Defense",
  description: "Autonomous cloud-native defensive DDoS telemetry, eBPF inspection, and fail-closed mitigation control plane.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        suppressHydrationWarning
        className="bg-[#090D16] text-[#F3F4F6] antialiased selection:bg-[#00FF9D]/30 selection:text-[#00FF9D]"
      >
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
