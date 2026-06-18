"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  BarChart3,
  Brain,
  Activity,
  ChevronRight,
  Search,
  ClipboardList,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  badge?: string;
}

const navItems: NavItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: <LayoutDashboard className="h-4 w-4" />,
  },
  {
    label: "Patients",
    href: "/patients",
    icon: <Users className="h-4 w-4" />,
  },
  {
    label: "Analytics",
    href: "/analytics",
    icon: <BarChart3 className="h-4 w-4" />,
  },
  {
    label: "Review History",
    href: "/review-history",
    icon: <ClipboardList className="h-4 w-4" />,
  },
  {
    label: "Search",
    href: "/search",
    icon: <Search className="h-4 w-4" />,
  },
  {
    label: "Learning",
    href: "/learning",
    icon: <Brain className="h-4 w-4" />,
    badge: "AI",
  },
];

export function Sidebar() {
  const pathname = usePathname();

  function isActive(href: string): boolean {
    if (href === "/dashboard") return pathname === "/dashboard" || pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside className="fixed left-0 top-0 z-30 flex h-full w-60 flex-col border-r border-slate-200 bg-white">
      {/* Brand */}
      <div className="flex h-14 items-center gap-2.5 border-b border-slate-100 px-5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-medical-blue-600">
          <Activity className="h-4 w-4 text-white" />
        </div>
        <div className="leading-none">
          <p className="text-sm font-bold text-slate-900">DischargePilot</p>
          <p className="text-[10px] text-slate-400 tracking-wide">AI Platform</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          Navigation
        </p>
        <ul className="space-y-0.5">
          {navItems.map((item) => {
            const active = isActive(item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors duration-150",
                    active
                      ? "bg-medical-blue-50 text-medical-blue-700"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  )}
                >
                  <span
                    className={cn(
                      "flex-shrink-0 transition-colors duration-150",
                      active ? "text-medical-blue-600" : "text-slate-400 group-hover:text-slate-600"
                    )}
                  >
                    {item.icon}
                  </span>
                  <span className="flex-1">{item.label}</span>
                  {item.badge && (
                    <span className="rounded-full bg-medical-blue-100 px-1.5 py-0.5 text-[10px] font-semibold text-medical-blue-700">
                      {item.badge}
                    </span>
                  )}
                  {active && (
                    <ChevronRight className="h-3 w-3 text-medical-blue-400" />
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2">
          <div className="h-2 w-2 rounded-full bg-clinical-green-500 animate-pulse" />
          <span className="text-xs text-slate-500">System operational</span>
        </div>
        <p className="mt-2 px-1 text-[10px] text-slate-400">Version 0.1.0 — Phase 7+8</p>
      </div>
    </aside>
  );
}
