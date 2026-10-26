"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bell,
  History as HistoryIcon,
  Shield,
  Sliders,
} from "@/components/ui/icons";

const routes = [
  { href: "/overview", label: "Overview", icon: Activity },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/mitigation", label: "Mitigation", icon: Shield },
  { href: "/history", label: "History", icon: HistoryIcon },
  { href: "/settings", label: "Settings", icon: Sliders },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav aria-label="Main navigation" className="sidebar">
      <div className="text-[10px] uppercase tracking-wider text-cyan-400/60 font-mono px-3 mb-2">
        Monitoring & Controls
      </div>
      {routes.map((route) => {
        const active = pathname === route.href;
        const Icon = route.icon;
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`sidebar-link flex items-center gap-3${active ? " sidebar-link-active" : ""}`}
            href={route.href}
            key={route.href}
          >
            <Icon className={`w-4 h-4 ${active ? "text-cyan-400" : "text-sky-300/50"}`} />
            <span>{route.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
