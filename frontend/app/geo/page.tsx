"use client";

import { useState, useEffect } from "react";
import FranceMap from "@/components/map/FranceMap";
import { Map, Store, BarChart3, Sparkles, RefreshCw, TrendingUp, AlertTriangle } from "lucide-react";
import { API_BASE, brandAPI } from "@/lib/api";

interface StoreGroup {
  competitor_id: number;
  competitor_name: string;
  total: number;
  color: string;
}

function getRankColor(rank: number, total: number) {
  if (total <= 1) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  const pct = rank / (total - 1);
  if (pct === 0) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  if (pct <= 0.33) return { bg: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-200" };
  if (pct <= 0.66) return { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-200" };
  return { bg: "bg-red-100", text: "text-red-600", border: "border-red-200" };
}

export default function GeoPage() {
  const [storeGroups, setStoreGroups] = useState<StoreGroup[]>([]);
  const [brandName, setBrandName] = useState<string | null>(null);
  const [brandStoreCount, setBrandStoreCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

        const [storeRes, brand] = await Promise.allSettled([
          fetch(`${API_BASE}/geo/competitor-stores`, { headers }).then(r => r.ok ? r.json() : null),
          brandAPI.getProfile(),
        ]);

        if (storeRes.status === "fulfilled" && storeRes.value) {
          const groups: StoreGroup[] = (storeRes.value.competitors || [])
            .sort((a: StoreGroup, b: StoreGroup) => b.total - a.total);
          setStoreGroups(groups);
        }

        if (brand.status === "fulfilled") {
          const b = brand.value as any;
          setBrandName(b.company_name || null);
        }

        // Brand's own stores
        try {
          const storesRes = await fetch(`${API_BASE}/geo/stores`, { headers });
          if (storesRes.ok) {
            const storesData = await storesRes.json();
            setBrandStoreCount(Array.isArray(storesData) ? storesData.length : (storesData.stores?.length || 0));
          }
        } catch {}
      } catch (err) {
        console.error("Failed to load geo data:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const totalStores = storeGroups.reduce((sum, g) => sum + g.total, 0);
  const leader = storeGroups[0];
  const brandGroup = storeGroups.find(g => brandName && g.competitor_name.toLowerCase() === brandName.toLowerCase());

  // Generate recommendations
  const recommendations: string[] = [];
  if (brandName && storeGroups.length > 1) {
    if (brandGroup && leader && leader.competitor_id !== brandGroup.competitor_id) {
      const gap = leader.total - brandGroup.total;
      if (gap > 50) {
        recommendations.push(
          `${leader.competitor_name} domine avec ${leader.total.toLocaleString()} points de vente contre ${brandGroup.total.toLocaleString()} pour ${brandName}. Identifier les zones a fort potentiel ou ${leader.competitor_name} est present mais pas ${brandName}.`
        );
      }
    }
    if (!brandGroup && brandStoreCount === 0) {
      recommendations.push(
        `Aucun magasin ${brandName} n'est reference. Importez vos points de vente (CSV ou manuellement) pour analyser votre couverture geographique.`
      );
    }
    if (storeGroups.length >= 3) {
      const last = storeGroups[storeGroups.length - 1];
      if (last.total < totalStores * 0.05) {
        recommendations.push(
          `${last.competitor_name} a une presence marginale (${last.total} magasins, ${(last.total / totalStores * 100).toFixed(1)}% du total). Opportunite de capter ses zones de chalandise.`
        );
      }
    }
    if (leader && leader.total > totalStores * 0.4) {
      recommendations.push(
        `${leader.competitor_name} concentre ${(leader.total / totalStores * 100).toFixed(0)}% des points de vente. Forte domination geographique — privilegier la differenciation sur les zones partagees.`
      );
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
          <Map className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">Carte & Zones</h1>
          <p className="text-[13px] text-muted-foreground">
            Analysez les zones de chalandise avec donn&eacute;es INSEE et loyers
          </p>
        </div>
      </div>

      {/* Competitive Intelligence Dashboard */}
      {!loading && storeGroups.length > 0 && (
        <div className="space-y-4">
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 shadow-md shadow-violet-200/50">
                  <Store className="h-3.5 w-3.5 text-white" />
                </div>
                <span className="text-xs font-medium text-muted-foreground">Total magasins</span>
              </div>
              <p className="text-lg font-bold text-foreground">{totalStores.toLocaleString()}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{storeGroups.length} enseignes</p>
            </div>
            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-md shadow-emerald-200/50">
                  <TrendingUp className="h-3.5 w-3.5 text-white" />
                </div>
                <span className="text-xs font-medium text-muted-foreground">Leader</span>
              </div>
              <p className="text-lg font-bold text-foreground">{leader?.competitor_name || "—"}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{leader ? `${leader.total.toLocaleString()} magasins (${(leader.total / totalStores * 100).toFixed(0)}%)` : ""}</p>
            </div>
            {brandGroup && (
              <div className="rounded-2xl border border-violet-200 bg-violet-50/50 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 shadow-md shadow-violet-200/50">
                    <Store className="h-3.5 w-3.5 text-white" />
                  </div>
                  <span className="text-xs font-medium text-muted-foreground">{brandName}</span>
                </div>
                <p className="text-lg font-bold text-violet-700">{brandGroup.total.toLocaleString()}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  #{storeGroups.indexOf(brandGroup) + 1} / {storeGroups.length} enseignes
                </p>
              </div>
            )}
            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-sky-600 shadow-md shadow-sky-200/50">
                  <BarChart3 className="h-3.5 w-3.5 text-white" />
                </div>
                <span className="text-xs font-medium text-muted-foreground">Concentration</span>
              </div>
              <p className="text-lg font-bold text-foreground">
                {leader ? `${(leader.total / totalStores * 100).toFixed(0)}%` : "—"}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Part du leader</p>
            </div>
          </div>

          {/* Store Distribution - Share of Voice style */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Store className="h-4 w-4 text-violet-500" />
              Repartition des points de vente
            </h2>
            <div className="space-y-3">
              {storeGroups.map((g, i) => {
                const isBrand = brandName && g.competitor_name.toLowerCase() === brandName.toLowerCase();
                const rc = getRankColor(i, storeGroups.length);
                const barColors: Record<string, string> = {
                  "text-emerald-700": "bg-emerald-500",
                  "text-yellow-700": "bg-yellow-500",
                  "text-orange-700": "bg-orange-500",
                  "text-red-600": "bg-red-500",
                };
                const barColor = isBrand ? "bg-gradient-to-r from-violet-500 to-indigo-500" : (barColors[rc.text] || "bg-gray-300");
                const pct = totalStores > 0 ? (g.total / totalStores * 100) : 0;
                return (
                  <div key={g.competitor_id} className="flex items-center gap-3">
                    <div className="flex items-center gap-2 w-32">
                      <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: g.color }} />
                      <span className={`text-sm font-medium truncate ${isBrand ? "text-violet-700 font-bold" : rc.text + " font-medium"}`}>
                        {g.competitor_name}
                      </span>
                    </div>
                    <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${barColor}`}
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                    </div>
                    <span className={`text-sm font-semibold w-14 text-right ${isBrand ? "text-violet-700" : rc.text}`}>
                      {pct.toFixed(1)}%
                    </span>
                    <span className="text-xs text-muted-foreground w-24 text-right">
                      {g.total.toLocaleString()} magasins
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <div className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-6">
              <h2 className="text-base font-semibold text-violet-800 mb-4 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Insights geographiques
              </h2>
              <div className="space-y-3">
                {recommendations.map((rec, i) => (
                  <div key={i} className="rounded-xl bg-white/80 border border-violet-100 p-4 text-sm text-violet-900">
                    {rec}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <FranceMap />
    </div>
  );
}
