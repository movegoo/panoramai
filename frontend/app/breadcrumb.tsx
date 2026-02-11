"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { brandAPI } from "@/lib/api";
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
  const [brandName, setBrandName] = useState<string | null>(null);

  useEffect(() => {
    brandAPI.getProfile().then((p) => setBrandName(p.company_name)).catch(() => {});
  }, []);

  return (
    <div className="h-12 shrink-0 border-b border-border bg-card/80 backdrop-blur-sm flex items-center justify-between px-6">
      {/* Breadcrumb trail */}
      <div className="flex items-center gap-1.5 text-[13px]">
        <span className="text-muted-foreground font-medium">panoram<span className="font-bold bg-gradient-to-r from-violet-600 to-indigo-500 bg-clip-text text-transparent">AI</span></span>
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
      {brandName && (
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-100 to-indigo-100 text-[11px] font-bold text-violet-700 border border-violet-200/50">
            {brandName.charAt(0).toUpperCase()}
          </div>
          <span className="text-[13px] font-semibold text-foreground">{brandName}</span>
        </div>
      )}
    </div>
  );
}
