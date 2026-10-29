import type { Metadata, Viewport } from "next";
import { AppShell } from "@/components/layout/AppShell";
import "./globals.css";

const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://sentrix.security";

export const viewport: Viewport = {
  themeColor: "#090D16",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(baseUrl),
  title: {
    default: "SENTRIX | Intelligent DDoS Detection & Defense Platform",
    template: "%s | SENTRIX Defense",
  },
  description:
    "Autonomous cloud-native defensive DDoS telemetry, statistical EWMA anomaly velocity analysis, and fail-closed mitigation control plane.",
  applicationName: "SENTRIX",
  authors: [{ name: "SENTRIX Security Engineering Team" }],
  generator: "Next.js",
  keywords: [
    "DDoS Detection",
    "DDoS Mitigation",
    "Cybersecurity",
    "EWMA Velocity",
    "Shannon Entropy",
    "Cloudflare WAF",
    "Nginx Rate Limiting",
    "DevSecOps",
  ],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: baseUrl,
    siteName: "SENTRIX",
    title: "SENTRIX — Intelligent DDoS Detection & Defense Platform",
    description:
      "Enterprise real-time HTTP telemetry streaming, adaptive anomaly detection, and automated WAF defensive enforcement.",
  },
  twitter: {
    card: "summary_large_image",
    title: "SENTRIX — Intelligent DDoS Detection & Defense Platform",
    description:
      "Enterprise real-time HTTP telemetry streaming, adaptive anomaly detection, and automated WAF defensive enforcement.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
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
