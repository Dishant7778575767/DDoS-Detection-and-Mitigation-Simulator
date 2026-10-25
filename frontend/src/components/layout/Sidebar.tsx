"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const routes = [
  { href: "/overview", label: "Overview" },
  { href: "/alerts", label: "Alerts" },
  { href: "/mitigation", label: "Mitigation" },
  { href: "/history", label: "History" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <nav aria-label="Main navigation" className="sidebar">
      {routes.map((route) => {
        const active = pathname === route.href;
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`sidebar-link${active ? " sidebar-link-active" : ""}`}
            href={route.href}
            key={route.href}
          >
            {route.label}
          </Link>
        );
      })}
    </nav>
  );
}
