"use client";

import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Megaphone,
  Activity,
  Smartphone,
  Map,
  Settings,
  ChevronRight,
} from "lucide-react";

const PAGE_META: Record<string, { label: string; icon: React.ElementType; parent?: string }> = {
  "/": { label: "Vue d\u2019ensemble", icon: LayoutDashboard, parent: "Dashboard" },
  "/geo": { label: "Carte & Zones", icon: Map, parent: "Dashboard" },
  "/competitors": { label: "Concurrents", icon: Users, parent: "Veille" },
  "/ads": { label: "Publicités", icon: Megaphone, parent: "Veille" },
  "/social": { label: "Réseaux sociaux", icon: Activity, parent: "Veille" },
  "/apps": { label: "Applications", icon: Smartphone, parent: "Veille" },
  "/account": { label: "Mon enseigne", icon: Settings, parent: "Paramètres" },
};

export function Breadcrumb() {
  const pathname = usePathname();
  const meta = PAGE_META[pathname] || PAGE_META["/"];
  const Icon = meta.icon;

  return (
    <div className="h-12 shrink-0 border-b border-border bg-card/80 backdrop-blur-sm flex items-center justify-between px-6">
      {/* Breadcrumb trail */}
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-muted-foreground font-medium">Panorama</span>
        <ChevronRight className="h-3 w-3 text-muted-foreground/50" />
        {meta.parent && (
          <>
            <span className="text-muted-foreground">{meta.parent}</span>
            <ChevronRight className="h-3 w-3 text-muted-foreground/50" />
          </>
        )}
        <span className="font-semibold text-foreground flex items-center gap-1.5">
          <Icon className="h-3.5 w-3.5 text-violet-600" />
          {meta.label}
        </span>
      </div>

      {/* Right side: brand info */}
      <div className="flex items-center gap-2.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-100 to-indigo-100 text-[11px] font-bold text-violet-700 border border-violet-200/50">
          A
        </div>
        <span className="text-[13px] font-semibold text-foreground">Auchan</span>
      </div>
    </div>
  );
}
