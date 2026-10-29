import type { ComponentType, SVGProps } from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  History as HistoryIcon,
  Server,
  Shield,
  Sliders,
  Zap,
} from "@/components/ui/icons";

export interface NavRoute {
  href: string;
  label: string;
  sublabel: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  badge?: string;
}

export const NAV_ROUTES: NavRoute[] = [
  {
    href: "/overview",
    label: "Overview",
    sublabel: "Live Traffic & AI Status",
    icon: Activity,
  },
  {
    href: "/telemetry",
    label: "Telemetry Stream",
    sublabel: "Real-Time L7 Ingestion",
    icon: Server,
    badge: "L7",
  },
  {
    href: "/threats",
    label: "Threat Center",
    sublabel: "Adaptive AI & Velocity",
    icon: AlertTriangle,
    badge: "AI",
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
    sublabel: "Dry-Run & Rate Limits",
    icon: Shield,
  },
  {
    href: "/simulator",
    label: "Cyber Range",
    sublabel: "Chaos Testbed Lab",
    icon: Zap,
    badge: "Lab",
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
    sublabel: "System Baselines",
    icon: Sliders,
  },
];
