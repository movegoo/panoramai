"use client";

import React, { useState, useMemo, useEffect } from "react";
import {
  Eye, RefreshCw, BarChart3, TrendingUp, AlertTriangle,
  Sparkles, Zap, Bot, Star, Search, MessageSquare,
} from "lucide-react";
import { geoTrackingAPI, GeoInsights, GeoQueryResult } from "@/lib/api";
import { useAPI } from "@/lib/use-api";
import { SmartFilter } from "@/components/smart-filter";

// ---------------------------------------------------------------------------
// Platform config
// ---------------------------------------------------------------------------
const LLM_CONFIG: Record<string, { label: string; color: string; bg: string; chartColor: string; icon: string }> = {
  mistral: { label: "Mistral", color: "text-orange-600", bg: "bg-orange-100", chartColor: "#ea580c", icon: "https://mistral.ai/favicon.ico" },
  claude: { label: "Claude", color: "text-amber-700", bg: "bg-amber-100", chartColor: "#b45309", icon: "https://claude.ai/favicon.ico" },
  gemini: { label: "Gemini", color: "text-blue-600", bg: "bg-blue-100", chartColor: "#2563eb", icon: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Google-gemini-icon.svg/3840px-Google-gemini-icon.svg.png" },
  chatgpt: { label: "ChatGPT", color: "text-emerald-600", bg: "bg-emerald-100", chartColor: "#059669", icon: "https://chatgpt.com/favicon.ico" },
};

const COMP_COLORS = [
  "#7c3aed", "#2563eb", "#059669", "#ea580c", "#dc2626",
  "#0891b2", "#7c2d12", "#4338ca", "#be123c", "#0d9488",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatDate(iso: string | null) {
  if (!iso) return "Jamais";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function getRankColor(rank: number, total: number) {
  if (total <= 1) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  const pct = rank / (total - 1);
  if (pct === 0) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  if (pct <= 0.33) return { bg: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-200" };
  if (pct <= 0.66) return { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-200" };
  return { bg: "bg-red-100", text: "text-red-600", border: "border-red-200" };
}

function getCellColor(value: number, allValues: number[]) {
  if (value === 0) return "bg-gray-50 text-gray-400";
  const sorted = Array.from(new Set(allValues)).sort((a, b) => b - a);
  const rank = sorted.indexOf(value);
  const total = sorted.filter(v => v > 0).length;
  if (total <= 1) return "bg-emerald-100 text-emerald-700 font-bold";
  const c = getRankColor(rank, total);
  return `${c.bg} ${c.text} font-bold`;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function VGeoPage() {
  const [aiFilters, setAiFilters] = useState<Record<string, any> | null>(null);
  const [aiInterpretation, setAiInterpretation] = useState("");

  // Data fetching
  const { data: insights, isLoading: loadingInsights, mutate: refreshInsights } = useAPI<GeoInsights>("/geo-tracking/insights");
  const { data: resData, isLoading: loadingResults, mutate: refreshResults } = useAPI<{ queries: GeoQueryResult[]; last_tracked: string | null }>("/geo-tracking/results");
  const { data: trendsData, isLoading: loadingTrends, mutate: refreshTrends } = useAPI<{
    trends: Record<string, any>[];
    competitors: { id: number; name: string }[];
    brand_name: string | null;
  }>("/geo-tracking/trends");

  const [tracking, setTracking] = useState(false);
  const [trackResult, setTrackResult] = useState<string | null>(null);

  const loading = loadingInsights || loadingResults;
  const results = resData?.queries || [];

  async function handleTrack() {
    setTracking(true);
    setTrackResult(null);
    try {
      const res = await geoTrackingAPI.track();
      setTrackResult(`${res.tracked_queries} requetes analysees sur ${res.platforms.length} plateformes IA, ${res.total_mentions} mentions detectees`);
      refreshInsights();
      refreshResults();
      refreshTrends();
    } catch (e: any) {
      setTrackResult(`Erreur: ${e.message}`);
    } finally {
      setTracking(false);
    }
  }

  // Brand info
  const brandId = insights?.brand_competitor_id;
  const brandName = insights?.brand_name || "Ma marque";
  const platforms = insights?.platforms || [];

  // KPI computations
  const brandSov = insights?.share_of_voice.find(s => s.competitor_id === brandId);
  const brandRec = insights?.recommendation_rate.find(r => r.competitor_id === brandId);
  const brandAvgPos = insights?.avg_position.find(a => a.competitor_id === brandId);
  const brandMissing = insights?.missing_keywords.find(m => m.competitor_id === brandId);

  // Competitor names
  const competitorNames: { name: string; id: number }[] = useMemo(() => {
    if (!insights) return [];
    const seen = new Set<number>();
    const names: { name: string; id: number }[] = [];
    insights.share_of_voice.forEach(s => {
      if (!seen.has(s.competitor_id)) {
        seen.add(s.competitor_id);
        names.push({ name: s.competitor, id: s.competitor_id });
      }
    });
    return names;
  }, [insights]);

  // AI Filter logic
  const filteredSov = useMemo(() => {
    if (!insights?.share_of_voice) return [];
    if (!aiFilters?.competitor_name?.length && !aiFilters?.text_search) return insights.share_of_voice;
    return insights.share_of_voice.filter(s => {
      const name = s.competitor.toLowerCase();
      if (aiFilters.competitor_name?.length) {
        return aiFilters.competitor_name.some((n: string) => name.includes(n.toLowerCase()));
      }
      if (aiFilters.text_search) return name.includes(aiFilters.text_search.toLowerCase());
      return true;
    });
  }, [insights?.share_of_voice, aiFilters]);

  const filteredResults = useMemo(() => {
    if (!results.length) return results;
    if (!aiFilters) return results;
    let filtered = [...results];
    if (aiFilters.keyword?.length) {
      const kws = aiFilters.keyword.map((k: string) => k.toLowerCase());
      filtered = filtered.filter(r => kws.some((k: string) => r.keyword.toLowerCase().includes(k)));
    }
    if (aiFilters.text_search) {
      const q = aiFilters.text_search.toLowerCase();
      filtered = filtered.filter(r => r.keyword.toLowerCase().includes(q));
    }
    return filtered;
  }, [results, aiFilters]);

  const filteredCompetitorNames = useMemo(() => {
    if (!aiFilters?.competitor_name?.length) return competitorNames;
    const names = aiFilters.competitor_name.map((n: string) => n.toLowerCase());
    return competitorNames.filter(c => names.some((n: string) => c.name.toLowerCase().includes(n)));
  }, [competitorNames, aiFilters]);

  // Empty state
  if (!loading && (!insights || insights.total_queries === 0)) {
    return (
      <div className="space-y-6">
        <VGeoHeader handleTrack={handleTrack} tracking={tracking} platforms={platforms} />
        <div className="rounded-2xl border bg-card p-8 text-center space-y-3">
          <div className="flex justify-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-100">
              <Eye className="h-6 w-6 text-violet-600" />
            </div>
          </div>
          <h3 className="text-sm font-semibold">Aucune donnee VGEO</h3>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Lancez une analyse GEO depuis la page GEO pour commencer le suivi de visibilite IA.
          </p>
          <button onClick={handleTrack} disabled={tracking}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-medium hover:bg-violet-700 disabled:opacity-50 transition-colors">
            {tracking ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
            {tracking ? "Analyse en cours..." : "Lancer l'analyse"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <VGeoHeader handleTrack={handleTrack} tracking={tracking} platforms={platforms} />

      {trackResult && (
        <div className="rounded-xl bg-violet-50 border border-violet-200 px-4 py-3 text-sm text-violet-700">
          {trackResult}
        </div>
      )}

      {/* Smart Filter */}
      <SmartFilter
        page="vgeo"
        placeholder="Filtrer la visibilite IA... (ex: Leclerc ChatGPT, sentiment positif, mot-cle livraison)"
        onFilter={(filters, interp) => { setAiFilters(filters); setAiInterpretation(interp); }}
        onClear={() => { setAiFilters(null); setAiInterpretation(""); }}
      />

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin text-violet-500" />
          <span className="ml-3 text-muted-foreground">Chargement des donnees VGEO...</span>
        </div>
      ) : insights ? (
        <>
          {/* ── Section 1: Hero KPIs ── */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <HeroCard
              label="Visibilite marque"
              value={brandSov ? `${brandSov.pct}%` : "0%"}
              subtitle={brandSov ? `${brandSov.mentions} mentions` : "Aucune mention"}
              icon={Eye}
              gradient="from-violet-500 to-violet-600"
              shadow="shadow-violet-200/50"
            />
            <HeroCard
              label="Taux recommandation"
              value={brandRec ? `${brandRec.rate}%` : "0%"}
              subtitle={brandRec ? `${brandRec.recommended_count}/${brandRec.total_mentions} reponses` : "Aucune"}
              icon={Star}
              gradient="from-indigo-500 to-indigo-600"
              shadow="shadow-indigo-200/50"
            />
            <HeroCard
              label="Position moyenne"
              value={brandAvgPos ? `#${brandAvgPos.avg_pos}` : "--"}
              subtitle="Dans les reponses IA"
              icon={TrendingUp}
              gradient="from-cyan-500 to-cyan-600"
              shadow="shadow-cyan-200/50"
            />
            <HeroCard
              label="Plateformes actives"
              value={String(platforms.length || 4)}
              subtitle={(platforms.length > 0 ? platforms : ["mistral", "claude", "gemini", "chatgpt"]).map(p => LLM_CONFIG[p]?.label || p).join(", ")}
              icon={Bot}
              gradient="from-teal-500 to-teal-600"
              shadow="shadow-teal-200/50"
            />
          </div>

          {/* ── Section 2: Share of Voice ── */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-violet-500" />
              Share of Voice IA
            </h2>
            <div className="space-y-3">
              {filteredSov.map((s, i) => {
                const isBrand = s.competitor_id === brandId;
                const rc = getRankColor(i, filteredSov.length);
                const barColors: Record<string, string> = {
                  "text-emerald-700": "bg-emerald-500",
                  "text-yellow-700": "bg-yellow-500",
                  "text-orange-700": "bg-orange-500",
                  "text-red-600": "bg-red-500",
                };
                const barColor = isBrand ? "bg-gradient-to-r from-violet-500 to-indigo-500" : (barColors[rc.text] || "bg-gray-300");
                return (
                  <div key={s.competitor_id} className="flex items-center gap-3">
                    <span className={`w-32 text-sm truncate flex items-center gap-1 ${isBrand ? "text-violet-700 font-bold" : rc.text + " font-medium"}`}>
                      {s.competitor}
                      {isBrand && <span className="text-[9px] font-bold text-violet-600 bg-violet-100 rounded px-1 py-0.5 shrink-0">vous</span>}
                    </span>
                    <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${barColor}`}
                        style={{ width: `${Math.max(s.pct, 2)}%` }}
                      />
                    </div>
                    <span className={`text-sm font-semibold w-16 text-right ${isBrand ? "text-violet-700" : rc.text}`}>
                      {s.pct}%
                    </span>
                    <span className="text-xs text-muted-foreground w-24 text-right">
                      {s.mentions} mentions
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ── Section 3: Comparaison Plateformes ── */}
          {insights.platform_comparison.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <Bot className="h-4 w-4 text-indigo-500" />
                Comparaison par plateforme IA
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Concurrent</th>
                      {(platforms.length > 0 ? platforms : ["mistral", "claude", "gemini", "chatgpt"]).map(p => (
                        <th key={p} className="text-center py-2 px-4">
                          <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${LLM_CONFIG[p]?.color || ""}`}>
                            {LLM_CONFIG[p] && <img src={LLM_CONFIG[p].icon} alt={LLM_CONFIG[p].label} className="h-5 w-5 rounded-sm object-contain" />}
                            {LLM_CONFIG[p]?.label || p}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {insights.platform_comparison
                      .filter(row => {
                        if (!aiFilters?.competitor_name?.length) return true;
                        const names = aiFilters.competitor_name.map((n: string) => n.toLowerCase());
                        return names.some((n: string) => (row.competitor || "").toLowerCase().includes(n));
                      })
                      .map((row: any) => {
                        const isBrand = row.competitor_id === brandId;
                        return (
                          <tr key={row.competitor_id} className={`border-b border-border/50 ${isBrand ? "bg-violet-50/50" : "hover:bg-muted/30"}`}>
                            <td className={`py-2.5 pr-4 font-medium ${isBrand ? "text-violet-700 font-bold" : "text-foreground"}`}>
                              {row.competitor}
                              {isBrand && <span className="ml-1.5 text-[9px] font-bold text-violet-600 bg-violet-100 rounded px-1.5 py-0.5">vous</span>}
                            </td>
                            {(platforms.length > 0 ? platforms : ["mistral", "claude", "gemini", "chatgpt"]).map(p => {
                              const pct = row[`${p}_pct`] ?? 0;
                              const mentions = row[`${p}_mentions`] ?? 0;
                              const allPcts = insights.platform_comparison.map((r: any) => r[`${p}_pct`] ?? 0);
                              const colorCls = getCellColor(pct, allPcts);
                              return (
                                <td key={p} className="text-center py-2.5 px-4">
                                  <span className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 ${colorCls}`}>
                                    <span className="text-sm">{pct}%</span>
                                    <span className="text-xs opacity-70">({mentions})</span>
                                  </span>
                                </td>
                              );
                            })}
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Section 4: Heatmap Keywords x Concurrents ── */}
          {filteredResults.length > 0 && (filteredCompetitorNames.length > 0 || competitorNames.length > 0) && (
            <div className="rounded-2xl border border-border bg-card p-6 overflow-x-auto">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <Search className="h-4 w-4 text-violet-500" />
                Heatmap : mots-cles x concurrents
              </h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Mot-cle</th>
                    {(aiFilters?.competitor_name?.length ? filteredCompetitorNames : competitorNames).map(c => {
                      const isBrand = c.id === brandId;
                      return (
                        <th key={c.id} className={`text-center py-2 px-2 text-xs font-semibold uppercase tracking-wider ${isBrand ? "text-violet-700 bg-violet-50/80" : "text-muted-foreground"}`}>
                          <div className="flex flex-col items-center gap-0.5">
                            {c.name}
                            {isBrand && <span className="text-[9px] font-bold text-violet-600 bg-violet-100 rounded px-1.5 py-0.5 normal-case tracking-normal">vous</span>}
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map(q => {
                    const displayComps = aiFilters?.competitor_name?.length ? filteredCompetitorNames : competitorNames;
                    const statusMap: Record<number, { mentioned: boolean; recommended: boolean }> = {};
                    displayComps.forEach(c => { statusMap[c.id] = { mentioned: false, recommended: false }; });

                    const allMentions = [
                      ...(q.platforms.mistral || []),
                      ...(q.platforms.claude || []),
                      ...(q.platforms.gemini || []),
                      ...(q.platforms.chatgpt || []),
                    ];
                    allMentions.forEach(m => {
                      if (m.competitor_id && statusMap[m.competitor_id] !== undefined) {
                        statusMap[m.competitor_id].mentioned = true;
                        if (m.recommended) statusMap[m.competitor_id].recommended = true;
                      }
                    });

                    return (
                      <tr key={q.keyword} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2.5 pr-4 font-medium text-foreground text-xs">{q.keyword}</td>
                        {displayComps.map(c => {
                          const st = statusMap[c.id];
                          const isBrand = c.id === brandId;
                          let cls = "bg-gray-100 border-gray-200 text-gray-400";
                          let label = "\u2014";
                          if (st?.mentioned && st?.recommended) {
                            cls = isBrand
                              ? "bg-violet-300 border-violet-400 text-violet-900 ring-2 ring-violet-400/50"
                              : "bg-emerald-200 border-emerald-300 text-emerald-800";
                            label = "\u2605";
                          } else if (st?.mentioned) {
                            cls = isBrand
                              ? "bg-violet-200 border-violet-300 text-violet-700 ring-2 ring-violet-300/50"
                              : "bg-yellow-100 border-yellow-200 text-yellow-700";
                            label = "\u2713";
                          } else {
                            cls = isBrand
                              ? "bg-red-100 border-red-200 text-red-400 ring-2 ring-red-200/50"
                              : "bg-gray-100 border-gray-200 text-gray-400";
                          }
                          return (
                            <td key={c.id} className={`text-center py-2.5 px-2 ${isBrand ? "bg-violet-50/50" : ""}`}>
                              <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg border text-xs font-bold ${cls}`}>
                                {label}
                              </span>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="flex items-center gap-4 mt-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded bg-emerald-200 border border-emerald-300 text-emerald-800 text-[10px] font-bold">{"\u2605"}</span>
                  Mentionne + Recommande
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded bg-yellow-100 border border-yellow-200 text-yellow-700 text-[10px] font-bold">{"\u2713"}</span>
                  Mentionne
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded bg-gray-100 border border-gray-200 text-gray-400 text-[10px] font-bold">{"\u2014"}</span>
                  Absent
                </span>
              </div>
            </div>
          )}

          {/* ── Section 5: Analyse Sentiment ── */}
          {insights.sentiment && insights.sentiment.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-violet-500" />
                Analyse Sentiment
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {insights.sentiment
                  .filter(s => {
                    if (!aiFilters?.competitor_name?.length) return true;
                    const names = aiFilters.competitor_name.map((n: string) => n.toLowerCase());
                    return names.some((n: string) => s.competitor.toLowerCase().includes(n));
                  })
                  .map(s => {
                    const isBrand = s.competitor_id === brandId;
                    const total = s.positive + s.neutral + s.negative || 1;
                    const posPct = Math.round(s.positive / total * 100);
                    const neuPct = Math.round(s.neutral / total * 100);
                    const negPct = 100 - posPct - neuPct;
                    return (
                      <div key={s.competitor_id} className={`rounded-xl border p-4 ${isBrand ? "border-violet-200 bg-violet-50/50 ring-1 ring-violet-200" : "border-border"}`}>
                        <div className="flex items-center gap-2 mb-3">
                          <span className={`text-sm font-semibold ${isBrand ? "text-violet-700" : "text-foreground"}`}>
                            {s.competitor}
                          </span>
                          {isBrand && <span className="text-[9px] font-bold text-violet-600 bg-violet-100 rounded px-1 py-0.5">vous</span>}
                        </div>
                        {/* Stacked bar */}
                        <div className="flex h-5 rounded-full overflow-hidden mb-2">
                          {posPct > 0 && <div className="bg-emerald-500 transition-all" style={{ width: `${posPct}%` }} />}
                          {neuPct > 0 && <div className="bg-yellow-400 transition-all" style={{ width: `${neuPct}%` }} />}
                          {negPct > 0 && <div className="bg-red-400 transition-all" style={{ width: `${negPct}%` }} />}
                        </div>
                        <div className="flex justify-between text-[10px] text-muted-foreground">
                          <span className="text-emerald-600 font-medium">{posPct}% positif</span>
                          <span className="text-yellow-600 font-medium">{neuPct}% neutre</span>
                          <span className="text-red-500 font-medium">{negPct}% negatif</span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {/* ── Section 6: Tendances temporelles ── */}
          {trendsData && trendsData.trends.length > 1 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-violet-500" />
                Tendances de visibilite
              </h2>
              <TrendChart
                data={trendsData.trends}
                competitors={trendsData.competitors}
                brandName={trendsData.brand_name}
                aiFilters={aiFilters}
              />
            </div>
          )}

          {/* ── Section 7: Mots-cles manquants ── */}
          {brandMissing && brandMissing.keywords.length > 0 && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-base font-semibold text-amber-800 mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                Mots-cles ou {brandName} est absent
              </h2>
              <p className="text-sm text-amber-700 mb-3">
                {brandName} n&apos;est mentionne par aucun moteur IA sur ces requetes. Travaillez votre presence sur ces sujets.
              </p>
              <div className="flex flex-wrap gap-2">
                {brandMissing.keywords.map(kw => (
                  <span key={kw} className="inline-flex items-center rounded-lg bg-amber-100 border border-amber-200 px-3 py-1.5 text-xs font-medium text-amber-800">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* ── Section 8: Analyse IA (diagnostic) ── */}
          {insights.ai_analysis ? (
            <div className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-6 space-y-5">
              <h2 className="text-base font-semibold text-violet-800 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Diagnostic IA — Visibilite GEO
              </h2>
              <p className="text-sm text-violet-900 leading-relaxed">{insights.ai_analysis.diagnostic}</p>

              {insights.ai_analysis.priorities?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-violet-700 uppercase tracking-wider mb-3">Priorites</h3>
                  <div className="space-y-2">
                    {insights.ai_analysis.priorities.map((p, i) => (
                      <div key={i} className="rounded-xl bg-white/80 border border-violet-100 p-4">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-semibold text-violet-900">{p.action}</span>
                          <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                            p.impact === "high" ? "bg-red-100 text-red-700" : p.impact === "medium" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600"
                          }`}>Impact {p.impact}</span>
                          <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                            p.effort === "low" ? "bg-green-100 text-green-700" : p.effort === "medium" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"
                          }`}>Effort {p.effort}</span>
                        </div>
                        <p className="text-xs text-violet-800/80">{p.detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {insights.ai_analysis.quick_wins?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-violet-700 uppercase tracking-wider mb-2">Quick wins</h3>
                  <div className="flex flex-wrap gap-2">
                    {insights.ai_analysis.quick_wins.map((qw, i) => (
                      <span key={i} className="inline-flex items-center rounded-lg bg-white/80 border border-violet-200 px-3 py-1.5 text-xs font-medium text-violet-800">
                        {qw}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {insights.ai_analysis.benchmark_insight && (
                <div className="rounded-lg bg-indigo-100/60 border border-indigo-200 px-4 py-3 text-xs text-indigo-800">
                  <span className="font-semibold">Benchmark :</span> {insights.ai_analysis.benchmark_insight}
                </div>
              )}
            </div>
          ) : insights.recommendations.length > 0 ? (
            <div className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-6">
              <h2 className="text-base font-semibold text-violet-800 mb-4 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Recommandations VGEO
              </h2>
              <div className="space-y-3">
                {insights.recommendations.map((rec, i) => (
                  <div key={i} className="rounded-xl bg-white/80 border border-violet-100 p-4 text-sm text-violet-900">
                    {rec}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function VGeoHeader({ handleTrack, tracking, platforms }: {
  handleTrack: () => void;
  tracking: boolean;
  platforms: string[];
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-200/50">
          <Eye className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">VGEO — Visibilite IA</h1>
          <p className="text-sm text-muted-foreground flex items-center gap-1 flex-wrap">
            Suivi de presence dans
            {(platforms.length > 0 ? platforms : ["mistral", "claude", "gemini", "chatgpt"]).map((p, i, arr) => (
              <span key={p} className="inline-flex items-center gap-1">
                {LLM_CONFIG[p] && <img src={LLM_CONFIG[p].icon} alt={LLM_CONFIG[p].label} className="h-4 w-4 rounded-sm object-contain" />}
                <span className="font-medium text-foreground/70">{LLM_CONFIG[p]?.label || p}</span>
                {i < arr.length - 1 && <span className="text-muted-foreground/50">,</span>}
              </span>
            ))}
          </p>
        </div>
      </div>
      <button
        onClick={handleTrack}
        disabled={tracking}
        className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-200/50 hover:shadow-xl hover:shadow-violet-300/50 transition-all disabled:opacity-50"
      >
        <RefreshCw className={`h-4 w-4 ${tracking ? "animate-spin" : ""}`} />
        {tracking ? "Analyse en cours..." : "Rafraichir"}
      </button>
    </div>
  );
}

function HeroCard({ label, value, subtitle, icon: Icon, gradient, shadow }: {
  label: string;
  value: string;
  subtitle: string;
  icon: any;
  gradient: string;
  shadow: string;
}) {
  return (
    <div className={`rounded-xl bg-gradient-to-br ${gradient} px-4 py-3 text-white shadow-lg ${shadow}`}>
      <div className="flex items-center gap-2 mb-1 opacity-90">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-[10px] font-medium uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-xl font-bold leading-tight">{value}</p>
      <p className="text-[11px] opacity-80 mt-0.5">{subtitle}</p>
    </div>
  );
}

function TrendChart({ data, competitors, brandName, aiFilters }: {
  data: Record<string, any>[];
  competitors: { id: number; name: string }[];
  brandName: string | null;
  aiFilters: Record<string, any> | null;
}) {
  // Filter competitors if AI filter active
  const displayComps = useMemo(() => {
    if (!aiFilters?.competitor_name?.length) return competitors;
    const names = aiFilters.competitor_name.map((n: string) => n.toLowerCase());
    return competitors.filter(c => names.some((n: string) => c.name.toLowerCase().includes(n)));
  }, [competitors, aiFilters]);

  if (data.length < 2 || displayComps.length === 0) {
    return <p className="text-sm text-muted-foreground">Pas assez de donnees pour afficher les tendances (minimum 2 points).</p>;
  }

  // Find max value for Y axis
  const allValues = data.flatMap(d => displayComps.map(c => (d[c.name] as number) || 0));
  const maxVal = Math.max(...allValues, 10);

  // Simple SVG line chart
  const chartW = 800;
  const chartH = 250;
  const padL = 50;
  const padR = 20;
  const padT = 20;
  const padB = 40;
  const plotW = chartW - padL - padR;
  const plotH = chartH - padT - padB;

  const xScale = (i: number) => padL + (i / (data.length - 1)) * plotW;
  const yScale = (v: number) => padT + plotH - (v / maxVal) * plotH;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full max-w-4xl" preserveAspectRatio="xMidYMid meet">
        {/* Y axis grid */}
        {[0, 25, 50, 75, 100].filter(v => v <= maxVal * 1.1).map(v => (
          <g key={v}>
            <line x1={padL} y1={yScale(v)} x2={chartW - padR} y2={yScale(v)} stroke="#e5e7eb" strokeDasharray="4,4" />
            <text x={padL - 8} y={yScale(v) + 4} textAnchor="end" className="text-[10px] fill-gray-400">{v}%</text>
          </g>
        ))}

        {/* X axis labels */}
        {data.map((d, i) => {
          const show = data.length <= 10 || i % Math.ceil(data.length / 8) === 0 || i === data.length - 1;
          if (!show) return null;
          return (
            <text key={i} x={xScale(i)} y={chartH - 8} textAnchor="middle" className="text-[9px] fill-gray-500">
              {String(d.date).slice(5)}
            </text>
          );
        })}

        {/* Lines */}
        {displayComps.map((comp, ci) => {
          const isBrand = comp.name === brandName;
          const color = isBrand ? "#7c3aed" : COMP_COLORS[ci % COMP_COLORS.length];
          const points = data.map((d, i) => `${xScale(i)},${yScale((d[comp.name] as number) || 0)}`).join(" ");
          return (
            <g key={comp.id}>
              <polyline
                points={points}
                fill="none"
                stroke={color}
                strokeWidth={isBrand ? 3 : 2}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={0.85}
              />
              {/* Dots */}
              {data.map((d, i) => (
                <circle
                  key={i}
                  cx={xScale(i)}
                  cy={yScale((d[comp.name] as number) || 0)}
                  r={isBrand ? 4 : 3}
                  fill={color}
                  opacity={0.9}
                />
              ))}
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-3 justify-center">
        {displayComps.map((comp, ci) => {
          const isBrand = comp.name === brandName;
          const color = isBrand ? "#7c3aed" : COMP_COLORS[ci % COMP_COLORS.length];
          return (
            <span key={comp.id} className={`inline-flex items-center gap-1.5 text-xs ${isBrand ? "font-bold" : "font-medium"}`}>
              <span className="inline-block w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              {comp.name}
              {isBrand && <span className="text-[9px] text-violet-600 bg-violet-100 rounded px-1 py-0.5">vous</span>}
            </span>
          );
        })}
      </div>
    </div>
  );
}
