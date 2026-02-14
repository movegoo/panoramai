"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { brandAPI } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  LayoutDashboard,
  Users,
  Megaphone,
  Instagram,
  Smartphone,
  MapPin,
  Settings,
  ChevronDown,
  BarChart3,
  Globe,
  Eye,
  TrendingUp,
  UserPlus,
  PieChart,
  Map,
  Layers,
  Youtube,
  Music,
  Star,
  Activity,
  LogOut,
  Shield,
  X,
  Sparkles,
} from "lucide-react";

const navigation = [
  {
    name: "Dashboard",
    items: [
      { name: "Vue d\u2019ensemble", href: "/", icon: LayoutDashboard },
      { name: "Carte & Zones", href: "/geo", icon: Map },
    ],
  },
  {
    name: "Veille",
    items: [
      { name: "Concurrents", href: "/competitors", icon: Users },
      { name: "Publicit\u00e9s", href: "/ads", icon: Megaphone },
      { name: "R\u00e9seaux sociaux", href: "/social", icon: Activity },
      { name: "Applications", href: "/apps", icon: Smartphone },
      { name: "SEO", href: "/seo", icon: Globe },
      { name: "GEO", href: "/geo-tracking", icon: Sparkles },
    ],
  },
  {
    name: "Param\u00e8tres",
    items: [
      { name: "Mon enseigne", href: "/account", icon: Settings },
    ],
  },
];

export function SidebarNav({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [brandName, setBrandName] = useState<string | null>(null);

  useEffect(() => {
    brandAPI.getProfile().then((p) => setBrandName(p.company_name)).catch(() => {});
  }, []);

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  function toggleSection(name: string) {
    setCollapsed((prev) => ({ ...prev, [name]: !prev[name] }));
  }

  return (
    <aside className="w-[220px] h-full flex flex-col border-r border-border bg-card shrink-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 shadow-md shadow-violet-200/50">
            <span className="text-sm font-bold text-white tracking-tight">P</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[15px] font-bold tracking-tight text-foreground leading-none">
              panoram<span className="bg-gradient-to-r from-violet-600 to-indigo-500 bg-clip-text text-transparent">AI</span>
            </span>
            <span className="text-[10px] text-muted-foreground leading-none mt-0.5">
              Veille concurrentielle
            </span>
          </div>
        </div>
        {/* Close button - mobile only */}
        {onClose && (
          <button
            onClick={onClose}
            className="lg:hidden flex h-7 w-7 items-center justify-center rounded-lg hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </div>

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-1">
        {[
          ...navigation,
          ...(user
            ? [{ name: "Admin", items: [{ name: "Backoffice", href: "/admin", icon: Shield }] }]
            : []),
        ].map((section) => {
          const isCollapsed = collapsed[section.name];
          const hasActive = section.items.some((item) => isActive(item.href));

          return (
            <div key={section.name}>
              {/* Section header */}
              <button
                onClick={() => toggleSection(section.name)}
                className="flex items-center justify-between w-full px-2 py-1.5 mb-0.5 group"
              >
                <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground group-hover:text-foreground transition-colors">
                  {section.name}
                </span>
                <ChevronDown
                  className={`h-3 w-3 text-muted-foreground/60 transition-transform duration-200 ${
                    isCollapsed ? "-rotate-90" : ""
                  }`}
                />
              </button>

              {/* Section items */}
              {!isCollapsed && (
                <div className="space-y-0.5">
                  {section.items.map((item) => {
                    const active = isActive(item.href);
                    return (
                      <Link
                        key={item.name}
                        href={item.href}
                        className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-all ${
                          active
                            ? "bg-gradient-to-r from-violet-50 to-indigo-50 text-violet-700 shadow-sm border border-violet-100/80"
                            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                        }`}
                      >
                        <item.icon
                          className={`h-[16px] w-[16px] shrink-0 ${
                            active ? "text-violet-600" : "text-muted-foreground/70"
                          }`}
                        />
                        <span className="truncate">{item.name}</span>
                        {active && (
                          <div className="ml-auto h-1.5 w-1.5 rounded-full bg-violet-500" />
                        )}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>

      {/* Footer user */}
      <div className="border-t border-border">
        <Link href="/account" className="block px-3 pt-3 pb-2 hover:bg-muted/50 transition-colors">
          <div className="flex items-center gap-2.5 px-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-indigo-500 text-white text-[11px] font-bold shadow-sm">
              {(user?.name || user?.email || "?").charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-foreground truncate leading-none">
                {brandName || "Mon enseigne"}
              </p>
              <p className="text-[10px] text-muted-foreground truncate leading-none mt-0.5">
                {user?.email || "Parametres"}
              </p>
            </div>
            <Settings className="h-3.5 w-3.5 text-muted-foreground/50 shrink-0" />
          </div>
        </Link>
        <button
          onClick={logout}
          className="flex items-center gap-2 w-full px-5 py-2 text-[11px] text-muted-foreground hover:text-red-600 hover:bg-red-50/50 transition-colors"
        >
          <LogOut className="h-3 w-3" />
          Deconnexion
        </button>
      </div>
    </aside>
  );
}
