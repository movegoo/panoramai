"use client";

import { useState, useEffect } from "react";
import { Sparkles, RefreshCw, Search, TrendingUp, BarChart3, AlertTriangle, Eye, Zap, Bot } from "lucide-react";
import { geoTrackingAPI, GeoInsights, GeoQueryResult } from "@/lib/api";

function formatDate(iso: string | null) {
  if (!iso) return "Jamais";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function GeoTrackingPage() {
  const [insights, setInsights] = useState<GeoInsights | null>(null);
  const [results, setResults] = useState<GeoQueryResult[]>([]);
  const [lastTracked, setLastTracked] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tracking, setTracking] = useState(false);
  const [trackResult, setTrackResult] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const [insData, resData] = await Promise.all([
        geoTrackingAPI.getInsights(),
        geoTrackingAPI.getResults(),
      ]);
      setInsights(insData);
      setResults(resData.queries);
      setLastTracked(resData.last_tracked || insData.last_tracked);
    } catch (e) {
      console.error("Failed to load GEO data:", e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  async function handleTrack() {
    setTracking(true);
    setTrackResult(null);
    try {
      const res = await geoTrackingAPI.track();
      setTrackResult(`${res.tracked_queries} requetes analysees sur ${res.platforms.length} plateformes IA, ${res.total_mentions} mentions detectees`);
      await loadData();
    } catch (e: any) {
      setTrackResult(`Erreur: ${e.message}`);
    } finally {
      setTracking(false);
    }
  }

  // Dynamic brand info from insights
  const brandId = insights?.brand_competitor_id;
  const brandName = insights?.brand_name || "Ma marque";
  const platforms = insights?.platforms || [];
  const platformLabel = platforms.length > 0 ? platforms.map(p => p === "chatgpt" ? "ChatGPT" : p.charAt(0).toUpperCase() + p.slice(1)).join(", ") : "Claude, Gemini & ChatGPT";

  // Derived
  const brandSov = insights?.share_of_voice.find(s => s.competitor_id === brandId);
  const brandMissing = insights?.missing_keywords.find(m => m.competitor_id === brandId);
  const brandGap = insights?.seo_vs_geo.find(g => g.competitor_id === brandId);

  // Hero cards
  const mostVisible = insights?.share_of_voice[0];
  const mostRecommended = insights?.recommendation_rate[0];

  // Competitor names for heatmap
  const competitorNames: { name: string; id: number }[] = [];
  if (insights) {
    const seen = new Set<number>();
    insights.share_of_voice.forEach(s => {
      if (!seen.has(s.competitor_id)) {
        seen.add(s.competitor_id);
        competitorNames.push({ name: s.competitor, id: s.competitor_id });
      }
    });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-cyan-600 shadow-lg shadow-teal-200/50">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">Visibilite IA (GEO)</h1>
            <p className="text-sm text-muted-foreground">Suivi de la presence de marque dans les reponses {platformLabel}</p>
          </div>
        </div>
        <button
          onClick={handleTrack}
          disabled={tracking}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-teal-600 to-cyan-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-teal-200/50 hover:shadow-xl hover:shadow-teal-300/50 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${tracking ? "animate-spin" : ""}`} />
          {tracking ? "Analyse en cours..." : "Analyser la visibilite"}
        </button>
      </div>

      {/* Track result banner */}
      {trackResult && (
        <div className="rounded-xl bg-teal-50 border border-teal-200 px-4 py-3 text-sm text-teal-700">
          {trackResult}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin text-teal-500" />
          <span className="ml-3 text-muted-foreground">Chargement des donnees GEO...</span>
        </div>
      ) : !insights || insights.total_queries === 0 ? (
        <div className="rounded-2xl border border-dashed border-teal-300 bg-teal-50/50 p-12 text-center">
          <Bot className="h-12 w-12 text-teal-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">Aucune donnee GEO</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Cliquez sur &quot;Analyser la visibilite&quot; pour interroger Claude, Gemini et ChatGPT sur vos mots-cles strategiques.
          </p>
        </div>
      ) : (
        <>
          {/* Hero Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-2xl bg-gradient-to-br from-teal-500 to-teal-600 p-5 text-white shadow-lg shadow-teal-200/50">
              <div className="flex items-center gap-2 mb-2 opacity-90">
                <Eye className="h-4 w-4" />
                <span className="text-xs font-medium uppercase tracking-wider">Marque la plus visible</span>
              </div>
              <p className="text-2xl font-bold">{mostVisible?.competitor || "\u2014"}</p>
              <p className="text-sm opacity-80 mt-1">{mostVisible?.pct}% de part de voix IA ({mostVisible?.mentions} mentions)</p>
            </div>
            <div className="rounded-2xl bg-gradient-to-br from-cyan-500 to-cyan-600 p-5 text-white shadow-lg shadow-cyan-200/50">
              <div className="flex items-center gap-2 mb-2 opacity-90">
                <Zap className="h-4 w-4" />
                <span className="text-xs font-medium uppercase tracking-wider">Plus recommandee</span>
              </div>
              <p className="text-2xl font-bold">{mostRecommended?.competitor || "\u2014"}</p>
              <p className="text-sm opacity-80 mt-1">Recommandee dans {mostRecommended?.rate}% des reponses</p>
            </div>
            <div className={`rounded-2xl p-5 text-white shadow-lg ${
              brandGap && brandGap.gap >= 0
                ? "bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-emerald-200/50"
                : "bg-gradient-to-br from-amber-500 to-amber-600 shadow-amber-200/50"
            }`}>
              <div className="flex items-center gap-2 mb-2 opacity-90">
                <TrendingUp className="h-4 w-4" />
                <span className="text-xs font-medium uppercase tracking-wider">Ecart SEO/GEO {brandName}</span>
              </div>
              <p className="text-2xl font-bold">
                {brandGap ? `${brandGap.gap > 0 ? "+" : ""}${brandGap.gap} pts` : "\u2014"}
              </p>
              <p className="text-sm opacity-80 mt-1">
                {brandGap ? `SEO ${brandGap.seo_pct}% vs GEO ${brandGap.geo_pct}%` : "Pas de donnees SEO"}
              </p>
            </div>
          </div>

          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard label="Requetes analysees" value={insights.total_queries.toString()} icon={Search} color="teal" />
            <KpiCard label="Plateformes IA" value={platforms.length.toString()} icon={Bot} color="cyan" subtitle={platformLabel} />
            <KpiCard label={`Visibilite ${brandName}`} value={brandSov ? `${brandSov.pct}%` : "0%"} icon={Eye} color="emerald" subtitle={brandSov ? `${brandSov.mentions} mentions` : undefined} />
            <KpiCard label="Derniere analyse" value={formatDate(lastTracked)} icon={Sparkles} color="sky" />
          </div>

          {/* Share of Voice IA */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-teal-500" />
              Part de voix IA
            </h2>
            <div className="space-y-3">
              {insights.share_of_voice.map((s) => {
                const isBrand = s.competitor_id === brandId;
                return (
                  <div key={s.competitor_id} className="flex items-center gap-3">
                    <span className={`w-28 text-sm font-medium truncate ${isBrand ? "text-teal-700 font-bold" : "text-foreground"}`}>
                      {s.competitor}
                    </span>
                    <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${isBrand ? "bg-gradient-to-r from-teal-500 to-cyan-500" : "bg-gray-300"}`}
                        style={{ width: `${Math.max(s.pct, 2)}%` }}
                      />
                    </div>
                    <span className={`text-sm font-semibold w-16 text-right ${isBrand ? "text-teal-700" : "text-muted-foreground"}`}>
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

          {/* Platform Comparison */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Bot className="h-4 w-4 text-cyan-500" />
              Comparaison plateformes : {platformLabel}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Concurrent</th>
                    {platforms.map((p) => (
                      <th key={p} className="text-center py-2 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {p === "chatgpt" ? "ChatGPT" : p.charAt(0).toUpperCase() + p.slice(1)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {insights.platform_comparison.map((row) => {
                    const isBrand = row.competitor_id === brandId;
                    return (
                      <tr key={row.competitor_id} className={`border-b border-border/50 ${isBrand ? "bg-teal-50/50" : "hover:bg-muted/30"}`}>
                        <td className={`py-2.5 pr-4 font-medium ${isBrand ? "text-teal-700 font-bold" : "text-foreground"}`}>{row.competitor}</td>
                        {platforms.map((p) => (
                          <td key={p} className="text-center py-2.5 px-4">
                            <span className="inline-flex items-center gap-1.5">
                              <span className="text-sm font-semibold">{row[`${p}_pct`] ?? 0}%</span>
                              <span className="text-xs text-muted-foreground">({row[`${p}_mentions`] ?? 0})</span>
                            </span>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Recommendation Rate */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Zap className="h-4 w-4 text-teal-500" />
              Taux de recommandation
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {insights.recommendation_rate.map((r, i) => {
                const isBrand = r.competitor_id === brandId;
                return (
                  <div key={r.competitor_id} className={`rounded-xl p-4 ${isBrand ? "bg-teal-50 border border-teal-200" : "bg-gray-50 border border-gray-200"}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-sm font-semibold ${isBrand ? "text-teal-700" : "text-foreground"}`}>
                        #{i + 1} {r.competitor}
                      </span>
                    </div>
                    <div className={`text-2xl font-bold ${isBrand ? "text-teal-600" : "text-foreground"}`}>
                      {r.rate}%
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      Recommande {r.recommended_count} fois
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Heatmap: keyword x competitor */}
          <div className="rounded-2xl border border-border bg-card p-6 overflow-x-auto">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Search className="h-4 w-4 text-teal-500" />
              Heatmap : mentions par mot-cle
            </h2>
            {results.length > 0 && competitorNames.length > 0 ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Mot-cle</th>
                    {competitorNames.map((c) => (
                      <th key={c.id} className="text-center py-2 px-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {c.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.map((q) => {
                    // Build mention status for each competitor across all platforms
                    const statusMap: Record<number, { mentioned: boolean; recommended: boolean }> = {};
                    competitorNames.forEach(c => { statusMap[c.id] = { mentioned: false, recommended: false }; });

                    const allMentions = [
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
                        {competitorNames.map((c) => {
                          const st = statusMap[c.id];
                          let cls = "bg-gray-100 border-gray-200";
                          let label = "\u2014";
                          if (st.mentioned && st.recommended) {
                            cls = "bg-teal-200 border-teal-300 text-teal-800";
                            label = "\u2605";
                          } else if (st.mentioned) {
                            cls = "bg-teal-100 border-teal-200 text-teal-600";
                            label = "\u2713";
                          } else {
                            cls = "bg-gray-100 border-gray-200 text-gray-400";
                          }
                          return (
                            <td key={c.id} className="text-center py-2.5 px-2">
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
            ) : (
              <p className="text-sm text-muted-foreground">Aucun resultat disponible.</p>
            )}
            <div className="flex items-center gap-4 mt-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded bg-teal-200 border border-teal-300 text-teal-800 text-[10px] font-bold">{"\u2605"}</span>
                Mentionne + Recommande
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded bg-teal-100 border border-teal-200 text-teal-600 text-[10px] font-bold">{"\u2713"}</span>
                Mentionne
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded bg-gray-100 border border-gray-200 text-gray-400 text-[10px] font-bold">{"\u2014"}</span>
                Absent
              </span>
            </div>
          </div>

          {/* Key Criteria */}
          {insights.key_criteria.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-cyan-500" />
                Criteres utilises par les IA
              </h2>
              <div className="flex flex-wrap gap-2">
                {insights.key_criteria.map((c) => (
                  <span key={c.criterion} className="inline-flex items-center rounded-lg bg-cyan-50 border border-cyan-200 px-3 py-1.5 text-xs font-medium text-cyan-800">
                    {c.criterion}
                    <span className="ml-1.5 bg-cyan-200 text-cyan-700 rounded-full px-1.5 py-0.5 text-[10px] font-bold">{c.count}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* SEO vs GEO */}
          {insights.seo_vs_geo.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-teal-500" />
                SEO vs GEO
              </h2>
              <div className="space-y-4">
                {insights.seo_vs_geo.map((g) => {
                  const isBrand = g.competitor_id === brandId;
                  const maxPct = Math.max(g.seo_pct, g.geo_pct, 1);
                  return (
                    <div key={g.competitor_id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className={`text-sm font-medium ${isBrand ? "text-teal-700 font-bold" : "text-foreground"}`}>{g.competitor}</span>
                        <span className={`text-xs font-semibold ${g.gap >= 0 ? "text-emerald-600" : "text-amber-600"}`}>
                          {g.gap > 0 ? "+" : ""}{g.gap} pts
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground w-8">SEO</span>
                        <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full bg-blue-400" style={{ width: `${(g.seo_pct / maxPct) * 100}%` }} />
                        </div>
                        <span className="text-xs font-semibold w-12 text-right text-blue-600">{g.seo_pct}%</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-[10px] text-muted-foreground w-8">GEO</span>
                        <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${isBrand ? "bg-gradient-to-r from-teal-500 to-cyan-500" : "bg-teal-400"}`} style={{ width: `${(g.geo_pct / maxPct) * 100}%` }} />
                        </div>
                        <span className={`text-xs font-semibold w-12 text-right ${isBrand ? "text-teal-700" : "text-teal-600"}`}>{g.geo_pct}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Missing Keywords Alert */}
          {brandMissing && brandMissing.keywords.length > 0 && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-base font-semibold text-amber-800 mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                Mots-cles ou {brandName} est absent des reponses IA
              </h2>
              <p className="text-sm text-amber-700 mb-3">
                {brandName} n&apos;est mentionne par aucun moteur IA sur ces requetes :
              </p>
              <div className="flex flex-wrap gap-2">
                {brandMissing.keywords.map((kw) => (
                  <span key={kw} className="inline-flex items-center rounded-lg bg-amber-100 border border-amber-200 px-3 py-1.5 text-xs font-medium text-amber-800">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {insights.recommendations.length > 0 && (
            <div className="rounded-2xl border border-teal-200 bg-gradient-to-br from-teal-50 to-cyan-50 p-6">
              <h2 className="text-base font-semibold text-teal-800 mb-4 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Recommandations GEO
              </h2>
              <div className="space-y-3">
                {insights.recommendations.map((rec, i) => (
                  <div key={i} className="rounded-xl bg-white/80 border border-teal-100 p-4 text-sm text-teal-900">
                    {rec}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function KpiCard({ label, value, icon: Icon, color, subtitle }: {
  label: string;
  value: string;
  icon: any;
  color: string;
  subtitle?: string;
}) {
  const colors: Record<string, string> = {
    teal: "from-teal-500 to-teal-600 shadow-teal-200/50",
    cyan: "from-cyan-500 to-cyan-600 shadow-cyan-200/50",
    emerald: "from-emerald-500 to-emerald-600 shadow-emerald-200/50",
    sky: "from-sky-500 to-sky-600 shadow-sky-200/50",
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br ${colors[color]} shadow-md`}>
          <Icon className="h-3.5 w-3.5 text-white" />
        </div>
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
      </div>
      <p className="text-lg font-bold text-foreground">{value}</p>
      {subtitle && <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>}
    </div>
  );
}
