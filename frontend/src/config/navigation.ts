import type { ComponentType, SVGProps } from "react";
import {
  Activity,
  AlertTriangle,
  Cloud,
  Cpu,
  HeartPulse,
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
    sublabel: "Traffic summary & system status",
    icon: Activity,
  },
  {
    href: "/traffic",
    label: "Live Traffic",
    sublabel: "Real-time incoming requests",
    icon: Server,
    badge: "Live",
  },
  {
    href: "/detection",
    label: "Attack Detection",
    sublabel: "Flagged traffic & security events",
    icon: AlertTriangle,
    badge: "AI",
  },
  {
    href: "/models",
    label: "Machine Learning",
    sublabel: "Trained model health & live test",
    icon: Cpu,
  },
  {
    href: "/protection",
    label: "Attack Protection",
    sublabel: "Firewall rules & active defense",
    icon: Shield,
  },
  {
    href: "/simulator",
    label: "Traffic Simulator",
    sublabel: "Safe test traffic generator",
    icon: Zap,
    badge: "Lab",
  },
  {
    href: "/integrations",
    label: "Integrations",
    sublabel: "AWS CloudFront & Kinesis",
    icon: Cloud,
  },
  {
    href: "/health",
    label: "System Health",
    sublabel: "Service status & audit log",
    icon: HeartPulse,
  },
  {
    href: "/settings",
    label: "Settings",
    sublabel: "Limits & safety rules",
    icon: Sliders,
  },
];
