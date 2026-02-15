"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { useAuth } from "@/lib/auth";
import {
  LayoutDashboard,
  Users,
  Megaphone,
  Activity,
  Smartphone,
  Map,
  Settings,
  ChevronRight,
  ChevronDown,
  Plus,
  Check,
} from "lucide-react";
import Link from "next/link";

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
  const { user, currentAdvertiserId, switchAdvertiser } = useAuth();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const advertisers = user?.advertisers || [];
  const currentAdv = advertisers.find((a) => a.id === currentAdvertiserId) || advertisers[0];

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
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

      {/* Right side: advertiser switcher */}
      {currentAdv && (
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setOpen(!open)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-muted/60 transition-colors"
          >
            {currentAdv.logo_url ? (
              <img src={currentAdv.logo_url} alt="" className="h-7 w-7 rounded-full object-contain bg-white border border-border/50" />
            ) : (
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-100 to-indigo-100 text-[11px] font-bold text-violet-700 border border-violet-200/50">
                {currentAdv.company_name.charAt(0).toUpperCase()}
              </div>
            )}
            <span className="text-[13px] font-semibold text-foreground">{currentAdv.company_name}</span>
            {advertisers.length > 1 && (
              <ChevronDown className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
            )}
          </button>

          {open && advertisers.length > 0 && (
            <div className="absolute right-0 top-full mt-1 w-64 rounded-lg border border-border bg-card shadow-lg z-50 py-1">
              <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Mes enseignes
              </div>
              {advertisers.map((adv) => (
                <button
                  key={adv.id}
                  onClick={() => {
                    if (adv.id !== currentAdvertiserId) {
                      switchAdvertiser(adv.id);
                    }
                    setOpen(false);
                  }}
                  className="flex items-center gap-2.5 w-full px-3 py-2 text-left hover:bg-muted/60 transition-colors"
                >
                  {adv.logo_url ? (
                    <img src={adv.logo_url} alt="" className="h-7 w-7 rounded-full object-contain bg-white border border-border/50 shrink-0" />
                  ) : (
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-100 to-indigo-100 text-[11px] font-bold text-violet-700 border border-violet-200/50 shrink-0">
                      {adv.company_name.charAt(0).toUpperCase()}
                    </div>
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-foreground truncate">{adv.company_name}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{adv.sector}</p>
                  </div>
                  {adv.id === currentAdvertiserId && (
                    <Check className="h-4 w-4 text-violet-600 shrink-0" />
                  )}
                </button>
              ))}
              <div className="border-t border-border mt-1 pt-1">
                <Link
                  href="/account?new=1"
                  onClick={() => setOpen(false)}
                  className="flex items-center gap-2.5 w-full px-3 py-2 text-left hover:bg-muted/60 transition-colors text-[13px] text-violet-600 font-medium"
                >
                  <Plus className="h-4 w-4" />
                  Ajouter une enseigne
                </Link>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
