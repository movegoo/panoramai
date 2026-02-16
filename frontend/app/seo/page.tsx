"use client";

import React, { useState, useEffect } from "react";
import { Globe, RefreshCw, Search, TrendingUp, AlertTriangle, Sparkles, ExternalLink, BarChart3 } from "lucide-react";
import { seoAPI, SeoInsights, SerpRanking } from "@/lib/api";

function formatDate(iso: string | null) {
  if (!iso) return "Jamais";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function PositionBadge({ position }: { position: number | null }) {
  if (!position) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-gray-100 text-gray-400 text-xs font-medium">—</span>;
  let cls = "bg-gray-100 text-gray-500";
  if (position <= 3) cls = "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200";
  else if (position <= 6) cls = "bg-amber-100 text-amber-700 ring-1 ring-amber-200";
  else cls = "bg-red-100 text-red-600 ring-1 ring-red-200";
  return <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-xs font-bold ${cls}`}>{position}</span>;
}

function getRankColor(rank: number, total: number) {
  if (total <= 1) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  const pct = rank / (total - 1); // 0 = best, 1 = worst
  if (pct === 0) return { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200" };
  if (pct <= 0.33) return { bg: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-200" };
  if (pct <= 0.66) return { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-200" };
  return { bg: "bg-red-100", text: "text-red-600", border: "border-red-200" };
}

export default function SeoPage() {
  const [insights, setInsights] = useState<SeoInsights | null>(null);
  const [rankings, setRankings] = useState<SerpRanking[]>([]);
  const [lastTracked, setLastTracked] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tracking, setTracking] = useState(false);
  const [trackResult, setTrackResult] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const [insData, rankData] = await Promise.all([
        seoAPI.getInsights(),
        seoAPI.getRankings(),
      ]);
      setInsights(insData);
      setRankings(rankData.keywords);
      setLastTracked(rankData.last_tracked || insData.last_tracked);
    } catch (e) {
      console.error("Failed to load SEO data:", e);
    } finally {
      setLoading(false);
    }
  }

  const autoTrackedRef = React.useRef(false);

  useEffect(() => {
    loadData().then(() => {
      // Will be called after state is set — check via ref below
    });
  }, []);

  // Do NOT auto-trigger SEO tracking — it costs API credits
  // User must click "Rafraichir les positions" manually

  async function handleTrack() {
    setTracking(true);
    setTrackResult(null);
    try {
      const res = await seoAPI.track();
      setTrackResult(`${res.tracked_keywords} mots-cles trackes, ${res.total_results} resultats, ${res.matched_competitors} matchs concurrents`);
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

  // Derived data
  const brandSov = insights?.share_of_voice.find(s => s.competitor_id === brandId);
  const brandAvg = insights?.avg_position.find(a => a.competitor_id === brandId);
  const brandMissing = insights?.missing_keywords.find(m => m.competitor_id === brandId);

  // Build competitor list for ranking grid (from rankings + insights)
  const competitorNames: string[] = [];
  if (insights || rankings.length > 0) {
    const nameSet = new Set<string>();
    // From share_of_voice
    insights?.share_of_voice.forEach(s => nameSet.add(s.competitor));
    // From avg_position
    insights?.avg_position.forEach(a => nameSet.add(a.competitor));
    // From rankings results (covers all competitors that appear in SERP)
    rankings.forEach(kw => {
      kw.results.forEach(r => {
        if (r.competitor_name) nameSet.add(r.competitor_name);
      });
    });
    competitorNames.push(...Array.from(nameSet));
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-lg shadow-blue-200/50">
            <Globe className="h-5 w-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-foreground">Positionnement SEO</h1>
            <p className="text-sm text-muted-foreground">Suivi des positions Google sur les mots-cles strategiques</p>
          </div>
        </div>
        <button
          onClick={handleTrack}
          disabled={tracking}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-200/50 hover:shadow-xl hover:shadow-blue-300/50 transition-all disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${tracking ? "animate-spin" : ""}`} />
          {tracking ? "Tracking en cours..." : "Rafraichir les positions"}
        </button>
      </div>

      {/* Track result banner */}
      {trackResult && (
        <div className="rounded-xl bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-700">
          {trackResult}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin text-blue-500" />
          <span className="ml-3 text-muted-foreground">Chargement des donnees SEO...</span>
        </div>
      ) : !insights || insights.total_keywords === 0 ? (
        <div className="rounded-2xl border bg-card p-8 text-center space-y-3">
          <div className="flex justify-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-100">
              <Globe className="h-6 w-6 text-blue-600" />
            </div>
          </div>
          <h3 className="text-sm font-semibold">Aucune donnee SEO pour cette enseigne</h3>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Cliquez sur &laquo;&nbsp;Tracker le SEO&nbsp;&raquo; pour lancer le suivi des positions Google.
          </p>
          <button onClick={handleTrack} disabled={tracking}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {tracking ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            {tracking ? "Analyse en cours..." : "Lancer l'analyse SEO"}
          </button>
        </div>
      ) : (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiCard
              label="Mots-cles trackes"
              value={insights.total_keywords.toString()}
              icon={Search}
              color="blue"
            />
            <KpiCard
              label={`Position moy. ${brandName}`}
              value={brandAvg ? brandAvg.avg_pos.toFixed(1) : "—"}
              icon={TrendingUp}
              color="indigo"
              subtitle={brandAvg ? `${brandAvg.keywords_in_top10} mots-cles dans le top 10` : undefined}
            />
            <KpiCard
              label={`Part de voix ${brandName}`}
              value={brandSov ? `${brandSov.pct}%` : "0%"}
              icon={BarChart3}
              color="violet"
              subtitle={brandSov ? `${brandSov.appearances} apparitions` : undefined}
            />
            <KpiCard
              label="Derniere collecte"
              value={formatDate(lastTracked)}
              icon={Globe}
              color="sky"
            />
          </div>

          {/* Share of Voice */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-blue-500" />
              Part de voix SEO
            </h2>
            <div className="space-y-3">
              {insights.share_of_voice.map((s, i) => {
                const isBrand = s.competitor_id === brandId;
                const rc = getRankColor(i, insights.share_of_voice.length);
                const barColors: Record<string, string> = {
                  "text-emerald-700": "bg-emerald-500",
                  "text-yellow-700": "bg-yellow-500",
                  "text-orange-700": "bg-orange-500",
                  "text-red-600": "bg-red-500",
                };
                const barColor = isBrand ? "bg-gradient-to-r from-blue-500 to-indigo-500" : (barColors[rc.text] || "bg-gray-300");
                return (
                  <div key={s.competitor_id} className="flex items-center gap-3">
                    <span className={`w-28 text-sm font-medium truncate ${isBrand ? "text-blue-700 font-bold" : rc.text + " font-medium"}`}>
                      {s.competitor}
                    </span>
                    <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${barColor}`}
                        style={{ width: `${Math.max(s.pct, 2)}%` }}
                      />
                    </div>
                    <span className={`text-sm font-semibold w-16 text-right ${isBrand ? "text-blue-700" : rc.text}`}>
                      {s.pct}%
                    </span>
                    <span className="text-xs text-muted-foreground w-20 text-right">
                      {s.appearances} apparitions
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Average Position */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-indigo-500" />
              Position moyenne
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {insights.avg_position.map((a, i) => {
                const isBrand = a.competitor_id === brandId;
                const rc = getRankColor(i, insights.avg_position.length);
                return (
                  <div key={a.competitor_id} className={`rounded-xl p-4 border ${rc.bg} ${rc.border} ${isBrand ? "ring-2 ring-blue-400" : ""}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-sm font-semibold ${rc.text}`}>
                        #{i + 1} {a.competitor}
                      </span>
                    </div>
                    <div className={`text-2xl font-bold ${rc.text}`}>
                      {a.avg_pos.toFixed(1)}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {a.keywords_in_top10} mots-cles en top 10
                    </p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Rankings Grid */}
          <div className="rounded-2xl border border-border bg-card p-6 overflow-x-auto">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Search className="h-4 w-4 text-blue-500" />
              Positions par mot-cle
            </h2>
            {rankings.length > 0 && competitorNames.length > 0 ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Mot-cle</th>
                    {competitorNames.map((name) => (
                      <th key={name} className="text-center py-2 px-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rankings.map((kw) => {
                    const posMap: Record<string, number | null> = {};
                    competitorNames.forEach(n => { posMap[n] = null; });
                    kw.results.forEach(r => {
                      if (r.competitor_name) posMap[r.competitor_name] = r.position;
                    });
                    return (
                      <tr key={kw.keyword} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2.5 pr-4 font-medium text-foreground">{kw.keyword}</td>
                        {competitorNames.map((name) => (
                          <td key={name} className="text-center py-2.5 px-2">
                            <PositionBadge position={posMap[name]} />
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-muted-foreground">Aucun ranking disponible.</p>
            )}
          </div>

          {/* Missing Keywords Alert */}
          {brandMissing && brandMissing.keywords.length > 0 && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
              <h2 className="text-base font-semibold text-amber-800 mb-3 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                Mots-cles manquants pour {brandName}
              </h2>
              <p className="text-sm text-amber-700 mb-3">
                {brandName} n&apos;apparait pas dans le top 10 Google pour les requetes suivantes :
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

          {/* Top Domains */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Globe className="h-4 w-4 text-blue-500" />
              Top domaines
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {insights.top_domains.slice(0, 10).map((d) => (
                <div key={d.domain} className="flex items-center gap-2 rounded-lg bg-gray-50 border border-gray-200 px-3 py-2">
                  <ExternalLink className="h-3 w-3 text-muted-foreground shrink-0" />
                  <span className="text-xs font-medium text-foreground truncate">{d.domain}</span>
                  <span className="ml-auto text-xs font-bold text-blue-600">{d.count}</span>
                </div>
              ))}
            </div>
          </div>

          {/* AI Analysis */}
          {insights.ai_analysis ? (
            <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50 p-6 space-y-5">
              <h2 className="text-base font-semibold text-blue-800 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Diagnostic IA — SEO
              </h2>
              <p className="text-sm text-blue-900 leading-relaxed">{insights.ai_analysis.diagnostic}</p>

              {insights.ai_analysis.priorities?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-3">Priorites</h3>
                  <div className="space-y-2">
                    {insights.ai_analysis.priorities.map((p, i) => (
                      <div key={i} className="rounded-xl bg-white/80 border border-blue-100 p-4">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-semibold text-blue-900">{p.action}</span>
                          <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                            p.impact === "high" ? "bg-red-100 text-red-700" : p.impact === "medium" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600"
                          }`}>Impact {p.impact}</span>
                          <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                            p.effort === "low" ? "bg-green-100 text-green-700" : p.effort === "medium" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"
                          }`}>Effort {p.effort}</span>
                        </div>
                        <p className="text-xs text-blue-800/80">{p.detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {insights.ai_analysis.quick_wins?.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-2">Quick wins</h3>
                  <div className="flex flex-wrap gap-2">
                    {insights.ai_analysis.quick_wins.map((qw, i) => (
                      <span key={i} className="inline-flex items-center rounded-lg bg-white/80 border border-blue-200 px-3 py-1.5 text-xs font-medium text-blue-800">
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
            <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50 p-6">
              <h2 className="text-base font-semibold text-blue-800 mb-4 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Recommandations SEO
              </h2>
              <div className="space-y-3">
                {insights.recommendations.map((rec, i) => (
                  <div key={i} className="rounded-xl bg-white/80 border border-blue-100 p-4 text-sm text-blue-900">
                    {rec}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
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
    blue: "from-blue-500 to-blue-600 shadow-blue-200/50",
    indigo: "from-indigo-500 to-indigo-600 shadow-indigo-200/50",
    violet: "from-violet-500 to-violet-600 shadow-violet-200/50",
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
