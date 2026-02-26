"use client";

import { useState, useEffect, useMemo } from "react";
import FranceMap from "@/components/map/FranceMap";
import { SmartFilter } from "@/components/smart-filter";
import { Map, Store, BarChart3, Sparkles, RefreshCw, TrendingUp, AlertTriangle, Target, Users, Star, MessageSquare, CheckCircle2, ExternalLink, Trophy, ThumbsDown } from "lucide-react";
import { API_BASE, brandAPI, geoAPI, GmbScoringData, GmbScoringCompetitor } from "@/lib/api";
import { useAuth } from "@/lib/auth";

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

function getScoreColor(score: number | null) {
  if (score === null) return "bg-gray-200";
  if (score >= 75) return "bg-emerald-500";
  if (score >= 55) return "bg-yellow-500";
  if (score >= 35) return "bg-orange-500";
  return "bg-red-500";
}

function getScoreTextColor(score: number | null) {
  if (score === null) return "text-gray-400";
  if (score >= 75) return "text-emerald-700";
  if (score >= 55) return "text-yellow-700";
  if (score >= 35) return "text-orange-700";
  return "text-red-600";
}

export default function GeoPage() {
  const { currentAdvertiserId } = useAuth();
  const [storeGroups, setStoreGroups] = useState<StoreGroup[]>([]);
  const [brandName, setBrandName] = useState<string | null>(null);
  const [brandStoreCount, setBrandStoreCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [catchmentData, setCatchmentData] = useState<any>(null);
  const [gmbScoring, setGmbScoring] = useState<GmbScoringData | null>(null);
  const [gmbLoading, setGmbLoading] = useState(true);
  const [aiFilters, setAiFilters] = useState<Record<string, any> | null>(null);
  const [aiInterpretation, setAiInterpretation] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const advId = typeof window !== "undefined" ? localStorage.getItem("current_advertiser_id") : null;
        if (advId) headers["X-Advertiser-Id"] = advId;

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

        // Catchment zones
        try {
          const catchRes = await fetch(`${API_BASE}/geo/catchment-zones?radius_km=10`, { headers });
          if (catchRes.ok) {
            setCatchmentData(await catchRes.json());
          }
        } catch {}

        // GMB Scoring
        try {
          const scoring = await geoAPI.getGmbScoring();
          setGmbScoring(scoring);
        } catch {}
        setGmbLoading(false);
      } catch (err) {
        console.error("Failed to load geo data:", err);
      } finally {
        setLoading(false);
        setGmbLoading(false);
      }
    }
    loadData();
  }, [currentAdvertiserId]);

  const filteredStoreGroups = useMemo(() => {
    if (!aiFilters || !storeGroups.length) return storeGroups;
    let result = [...storeGroups];
    if (aiFilters.competitor_name?.length) {
      const names = aiFilters.competitor_name.map((n: string) => n.toLowerCase());
      result = result.filter((g: any) => names.some((n: string) => g.competitor_name.toLowerCase().includes(n)));
    }
    if (aiFilters.text_search) {
      const q = aiFilters.text_search.toLowerCase();
      result = result.filter((g: any) => g.competitor_name.toLowerCase().includes(q));
    }
    return result;
  }, [storeGroups, aiFilters]);

  const filteredGmbCompetitors = useMemo(() => {
    if (!aiFilters || !gmbScoring?.competitors?.length) return gmbScoring?.competitors || [];
    let result = [...gmbScoring.competitors];
    if (aiFilters.competitor_name?.length) {
      const names = aiFilters.competitor_name.map((n: string) => n.toLowerCase());
      result = result.filter((c: any) => names.some((n: string) => c.name.toLowerCase().includes(n)));
    }
    if (aiFilters.score_min) {
      result = result.filter((c: any) => (c.score || 0) >= aiFilters.score_min);
    }
    if (aiFilters.rating_min) {
      result = result.filter((c: any) => (c.avg_rating || 0) >= aiFilters.rating_min);
    }
    if (aiFilters.text_search) {
      const q = aiFilters.text_search.toLowerCase();
      result = result.filter((c: any) => c.name.toLowerCase().includes(q));
    }
    return result;
  }, [gmbScoring?.competitors, aiFilters]);

  const totalStores = filteredStoreGroups.reduce((sum, g) => sum + g.total, 0);
  const leader = filteredStoreGroups[0];
  const brandGroup = filteredStoreGroups.find(g => brandName && g.competitor_name.toLowerCase() === brandName.toLowerCase());

  // Generate recommendations
  const recommendations: string[] = [];
  if (brandName && filteredStoreGroups.length > 1) {
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
    if (filteredStoreGroups.length >= 3) {
      const last = filteredStoreGroups[filteredStoreGroups.length - 1];
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

  // GMB scoring helpers
  const gmbLeader = filteredGmbCompetitors[0];
  const brandGmb = filteredGmbCompetitors.find(c => brandName && c.competitor_name.toLowerCase() === brandName.toLowerCase());

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

      <SmartFilter
        page="geo"
        placeholder="Filtrer la géographie... (ex: Leclerc, score > 80, Île-de-France)"
        onFilter={(filters, interpretation) => { setAiFilters(filters); setAiInterpretation(interpretation); }}
        onClear={() => { setAiFilters(null); setAiInterpretation(""); }}
      />

      {/* Map + KPI summary side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* France Map — takes 2/3 */}
        <div className="lg:col-span-2">
          <FranceMap />
        </div>

        {/* Compact KPIs sidebar — takes 1/3 */}
        <div className="space-y-3">
          {/* Store KPIs */}
          {!loading && filteredStoreGroups.length > 0 && (
            <>
              <div className="rounded-2xl border border-border bg-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Store className="h-4 w-4 text-violet-500" />
                  <span className="text-sm font-semibold text-foreground">Points de vente</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-2xl font-bold text-foreground">{totalStores.toLocaleString()}</p>
                    <p className="text-[11px] text-muted-foreground">{filteredStoreGroups.length} enseignes</p>
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-foreground">{leader?.competitor_name || "—"}</p>
                    <p className="text-[11px] text-muted-foreground">{leader ? `${leader.total.toLocaleString()} (${(leader.total / totalStores * 100).toFixed(0)}%)` : "Leader"}</p>
                  </div>
                </div>
                {brandGroup && (
                  <div className="mt-3 pt-3 border-t border-border">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-violet-700">{brandName}</span>
                      <span className="text-xs font-bold text-violet-700">{brandGroup.total.toLocaleString()} mag. — #{filteredStoreGroups.indexOf(brandGroup) + 1}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Compact store distribution */}
              <div className="rounded-2xl border border-border bg-card p-4">
                <h3 className="text-xs font-semibold text-foreground mb-2 flex items-center gap-1.5">
                  <BarChart3 className="h-3.5 w-3.5 text-violet-500" />
                  Repartition
                </h3>
                <div className="space-y-1.5">
                  {filteredStoreGroups.slice(0, 6).map((g, i) => {
                    const isBrand = brandName && g.competitor_name.toLowerCase() === brandName.toLowerCase();
                    const pct = totalStores > 0 ? (g.total / totalStores * 100) : 0;
                    return (
                      <div key={g.competitor_id}>
                        <div className="flex items-center justify-between mb-0.5">
                          <div className="flex items-center gap-1.5">
                            <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: g.color }} />
                            <span className={`text-[11px] truncate ${isBrand ? "text-violet-700 font-bold" : "text-foreground"}`}>
                              {g.competitor_name}
                            </span>
                          </div>
                          <span className={`text-[11px] font-semibold ${isBrand ? "text-violet-700" : "text-muted-foreground"}`}>{pct.toFixed(0)}%</span>
                        </div>
                        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${isBrand ? "bg-gradient-to-r from-violet-500 to-indigo-500" : "bg-gray-400"}`}
                            style={{ width: `${Math.max(pct, 2)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                  {filteredStoreGroups.length > 6 && (
                    <p className="text-[10px] text-muted-foreground text-center pt-1">+{filteredStoreGroups.length - 6} autres</p>
                  )}
                </div>
              </div>
            </>
          )}

          {/* GMB summary */}
          {!gmbLoading && gmbScoring && filteredGmbCompetitors.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <Star className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-semibold text-foreground">Google My Business</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-2xl font-bold text-foreground">{gmbScoring.market_avg_score}<span className="text-sm font-normal text-muted-foreground">/100</span></p>
                  <p className="text-[11px] text-muted-foreground">Score moyen</p>
                </div>
                <div>
                  <div className="flex items-center gap-1">
                    <Star className="h-3.5 w-3.5 text-yellow-400 fill-yellow-400" />
                    <p className="text-2xl font-bold text-foreground">{gmbScoring.market_avg_rating.toFixed(1)}</p>
                  </div>
                  <p className="text-[11px] text-muted-foreground">{gmbScoring.total_reviews.toLocaleString()} avis</p>
                </div>
              </div>
              {brandGmb && (
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-violet-700">{brandName}</span>
                    <span className="text-xs font-bold text-violet-700">{brandGmb.avg_score ?? "—"}/100 — #{brandGmb.rank}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* GMB Detailed Scoring Section */}
      {!gmbLoading && gmbScoring && filteredGmbCompetitors.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Star className="h-4.5 w-4.5 text-amber-500" />
            Scoring Google My Business — Detail
          </h2>

          {/* Competitor Ranking Table */}
          <div className="rounded-2xl border border-border bg-card overflow-hidden">
            <div className="px-5 py-3 border-b border-border bg-gray-50/50">
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Trophy className="h-4 w-4 text-amber-500" />
                Classement GMB par enseigne
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-gray-50/30">
                    <th className="text-left py-2.5 px-4 font-medium text-muted-foreground w-10">#</th>
                    <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">Enseigne</th>
                    <th className="text-left py-2.5 px-4 font-medium text-muted-foreground">Score GMB</th>
                    <th className="text-center py-2.5 px-4 font-medium text-muted-foreground">Rating</th>
                    <th className="text-right py-2.5 px-4 font-medium text-muted-foreground">Avis</th>
                    <th className="text-center py-2.5 px-4 font-medium text-muted-foreground">Completude</th>
                    <th className="text-right py-2.5 px-4 font-medium text-muted-foreground">Magasins</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredGmbCompetitors.map((comp) => {
                    const isBrand = brandName && comp.competitor_name.toLowerCase() === brandName.toLowerCase();
                    const scorePct = comp.avg_score !== null ? comp.avg_score : 0;
                    return (
                      <tr
                        key={comp.competitor_id}
                        className={`border-b border-border last:border-0 hover:bg-gray-50/50 transition-colors ${isBrand ? "bg-violet-50/40" : ""}`}
                      >
                        <td className="py-2.5 px-4">
                          <span className={`text-xs font-bold ${comp.rank <= 3 ? "text-amber-600" : "text-muted-foreground"}`}>
                            {comp.rank}
                          </span>
                        </td>
                        <td className="py-2.5 px-4">
                          <div className="flex items-center gap-2">
                            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: comp.color }} />
                            {comp.logo_url && (
                              <img src={comp.logo_url} alt="" className="w-5 h-5 rounded object-contain" />
                            )}
                            <span className={`font-medium truncate ${isBrand ? "text-violet-700 font-bold" : "text-foreground"}`}>
                              {comp.competitor_name}
                              {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                            </span>
                          </div>
                        </td>
                        <td className="py-2.5 px-4">
                          <div className="flex items-center gap-2">
                            <div className="w-20 h-2 bg-gray-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${isBrand ? "bg-gradient-to-r from-violet-500 to-indigo-500" : getScoreColor(comp.avg_score)}`}
                                style={{ width: `${Math.max(scorePct, 2)}%` }}
                              />
                            </div>
                            <span className={`font-bold ${isBrand ? "text-violet-700" : getScoreTextColor(comp.avg_score)}`}>
                              {comp.avg_score ?? "—"}
                            </span>
                          </div>
                        </td>
                        <td className="py-2.5 px-4 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                            <span className="font-semibold">{comp.avg_rating?.toFixed(1) ?? "—"}</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-4 text-right font-medium">
                          {comp.total_reviews.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-4 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            comp.completeness_pct >= 80 ? "bg-emerald-100 text-emerald-700" :
                            comp.completeness_pct >= 50 ? "bg-yellow-100 text-yellow-700" :
                            "bg-red-100 text-red-600"
                          }`}>
                            {comp.completeness_pct}%
                          </span>
                        </td>
                        <td className="py-2.5 px-4 text-right text-muted-foreground">
                          {comp.stores_with_rating}/{comp.stores_count}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Top 5 / Flop 5 Stores */}
          {filteredGmbCompetitors.some(c => c.top_stores.length > 0) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Top 5 */}
              <div className="rounded-2xl border border-emerald-200 bg-card p-5">
                <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-emerald-500" />
                  Top magasins
                </h3>
                <div className="space-y-2">
                  {filteredGmbCompetitors
                    .flatMap(c => c.top_stores.map(s => ({ ...s, competitor_name: c.competitor_name, color: c.color })))
                    .sort((a, b) => (b.gmb_score ?? 0) - (a.gmb_score ?? 0))
                    .slice(0, 5)
                    .map((s, i) => (
                      <div key={s.id} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs font-bold text-emerald-600 w-5">{i + 1}</span>
                          <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-foreground truncate">{s.name}</div>
                            <div className="text-[10px] text-muted-foreground">{s.city} — {s.competitor_name}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0 ml-2">
                          <div className="flex items-center gap-1">
                            <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                            <span className="text-xs font-semibold">{s.rating?.toFixed(1) ?? "—"}</span>
                          </div>
                          <span className="text-[10px] text-muted-foreground">{s.reviews_count?.toLocaleString() ?? "—"} avis</span>
                          <span className={`text-xs font-bold ${getScoreTextColor(s.gmb_score)}`}>{s.gmb_score ?? "—"}</span>
                          {s.place_id && (
                            <a
                              href={`https://www.google.com/maps/place/?q=place_id:${s.place_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:text-blue-700"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Flop 5 */}
              <div className="rounded-2xl border border-red-200 bg-card p-5">
                <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <ThumbsDown className="h-4 w-4 text-red-500" />
                  Magasins a ameliorer
                </h3>
                <div className="space-y-2">
                  {filteredGmbCompetitors
                    .flatMap(c => (c.flop_stores.length > 0 ? c.flop_stores : c.top_stores.slice(-2)).map(s => ({ ...s, competitor_name: c.competitor_name, color: c.color })))
                    .sort((a, b) => (a.gmb_score ?? 999) - (b.gmb_score ?? 999))
                    .slice(0, 5)
                    .map((s, i) => (
                      <div key={s.id} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs font-bold text-red-500 w-5">{i + 1}</span>
                          <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-foreground truncate">{s.name}</div>
                            <div className="text-[10px] text-muted-foreground">{s.city} — {s.competitor_name}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0 ml-2">
                          <div className="flex items-center gap-1">
                            <Star className="h-3 w-3 text-yellow-400 fill-yellow-400" />
                            <span className="text-xs font-semibold">{s.rating?.toFixed(1) ?? "—"}</span>
                          </div>
                          <span className="text-[10px] text-muted-foreground">{s.reviews_count?.toLocaleString() ?? "—"} avis</span>
                          <span className={`text-xs font-bold ${getScoreTextColor(s.gmb_score)}`}>{s.gmb_score ?? "—"}</span>
                          {s.place_id && (
                            <a
                              href={`https://www.google.com/maps/place/?q=place_id:${s.place_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:text-blue-700"
                            >
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Detailed Store Distribution + Population Coverage */}
      {!loading && filteredStoreGroups.length > 0 && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Full Store Distribution */}
            <div className="rounded-2xl border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                <Store className="h-4 w-4 text-violet-500" />
                Repartition des points de vente
              </h2>
              <div className="space-y-2">
                {filteredStoreGroups.map((g, i) => {
                  const isBrand = brandName && g.competitor_name.toLowerCase() === brandName.toLowerCase();
                  const rc = getRankColor(i, filteredStoreGroups.length);
                  const barColors: Record<string, string> = {
                    "text-emerald-700": "bg-emerald-500",
                    "text-yellow-700": "bg-yellow-500",
                    "text-orange-700": "bg-orange-500",
                    "text-red-600": "bg-red-500",
                  };
                  const barColor = isBrand ? "bg-gradient-to-r from-violet-500 to-indigo-500" : (barColors[rc.text] || "bg-gray-300");
                  const pct = totalStores > 0 ? (g.total / totalStores * 100) : 0;
                  return (
                    <div key={g.competitor_id}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: g.color }} />
                          <span className={`text-xs font-medium truncate ${isBrand ? "text-violet-700 font-bold" : "text-foreground"}`}>
                            {g.competitor_name}
                            {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-semibold ${isBrand ? "text-violet-700" : rc.text}`}>
                            {pct.toFixed(1)}%
                          </span>
                          <span className="text-[11px] text-muted-foreground">
                            {g.total.toLocaleString()}
                          </span>
                        </div>
                      </div>
                      <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${barColor}`}
                          style={{ width: `${Math.max(pct, 2)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Population Coverage */}
            {catchmentData && catchmentData.competitors?.length > 0 && (
              <div className="rounded-2xl border border-border bg-card p-5">
                <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <Target className="h-4 w-4 text-purple-500" />
                  Couverture population
                  <span className="text-[11px] font-normal text-muted-foreground ml-auto">
                    Rayon {catchmentData.radius_km} km
                  </span>
                </h2>
                <div className="space-y-2">
                  {catchmentData.competitors.map((comp: any, i: number) => {
                    const isBrand = brandName && comp.competitor_name.toLowerCase() === brandName.toLowerCase();
                    const rc = getRankColor(i, catchmentData.competitors.length);
                    const barColors: Record<string, string> = {
                      "text-emerald-700": "bg-emerald-500",
                      "text-yellow-700": "bg-yellow-500",
                      "text-orange-700": "bg-orange-500",
                      "text-red-600": "bg-red-500",
                    };
                    const barColor = isBrand ? "bg-gradient-to-r from-violet-500 to-indigo-500" : (barColors[rc.text] || "bg-gray-300");
                    return (
                      <div key={comp.competitor_id}>
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: comp.color }} />
                            <span className={`text-xs font-medium truncate ${isBrand ? "text-violet-700 font-bold" : "text-foreground"}`}>
                              {comp.competitor_name}
                              {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`text-xs font-semibold ${isBrand ? "text-violet-700" : rc.text}`}>
                              {comp.pct_population}%
                            </span>
                            <span className="text-[11px] text-muted-foreground">
                              {(comp.population_covered / 1000000).toFixed(1)}M
                            </span>
                          </div>
                        </div>
                        <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${barColor}`}
                            style={{ width: `${Math.max(comp.pct_population, 2)}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
                {catchmentData.overlaps?.length > 0 && (
                  <div className="mt-3 pt-3 border-t">
                    <div className="text-[11px] font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
                      <Users className="h-3 w-3" />
                      Zones de chevauchement
                    </div>
                    <div className="space-y-1.5">
                      {catchmentData.overlaps.slice(0, 4).map((o: any, i: number) => (
                        <div key={i} className="rounded-lg bg-gray-50 px-2.5 py-1.5 flex items-center justify-between">
                          <span className="text-[11px] text-gray-600 truncate">{o.competitor_a_name} / {o.competitor_b_name}</span>
                          <span className="text-[11px] font-semibold text-purple-700 ml-2 whitespace-nowrap">
                            {(o.shared_population / 1000000).toFixed(1)}M hab.
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
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
    </div>
  );
}
