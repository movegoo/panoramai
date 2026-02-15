"use client";

import { useState, useEffect } from "react";
import { Globe, RefreshCw, Search, TrendingUp, AlertTriangle, Sparkles, ExternalLink, BarChart3, MousePointerClick, Eye, ArrowRight, PlugZap } from "lucide-react";
import { seoAPI, gscAPI, SeoInsights, SerpRanking, GscStatus, GscPerformance, GscQueryRow, GscPageRow } from "@/lib/api";
import Link from "next/link";

function formatDate(iso: string | null) {
  if (!iso) return "Jamais";
  const d = new Date(iso);
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString("fr-FR");
}

function PositionBadge({ position }: { position: number | null }) {
  if (!position) return <span className="inline-flex items-center justify-center w-8 h-8 rounded-lg bg-gray-100 text-gray-400 text-xs font-medium">—</span>;
  let cls = "bg-gray-100 text-gray-500";
  if (position <= 3) cls = "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200";
  else if (position <= 6) cls = "bg-amber-100 text-amber-700 ring-1 ring-amber-200";
  else cls = "bg-red-100 text-red-600 ring-1 ring-red-200";
  return <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg text-xs font-bold ${cls}`}>{position}</span>;
}

const PERIOD_OPTIONS = [
  { value: "7d", label: "7 jours" },
  { value: "28d", label: "28 jours" },
  { value: "3m", label: "3 mois" },
];

export default function SeoPage() {
  // SERP data (existing)
  const [insights, setInsights] = useState<SeoInsights | null>(null);
  const [rankings, setRankings] = useState<SerpRanking[]>([]);
  const [lastTracked, setLastTracked] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tracking, setTracking] = useState(false);
  const [trackResult, setTrackResult] = useState<string | null>(null);

  // GSC data
  const [gscStatus, setGscStatus] = useState<GscStatus | null>(null);
  const [gscPerf, setGscPerf] = useState<GscPerformance | null>(null);
  const [gscQueries, setGscQueries] = useState<GscQueryRow[]>([]);
  const [gscPages, setGscPages] = useState<GscPageRow[]>([]);
  const [gscPeriod, setGscPeriod] = useState("28d");
  const [gscLoading, setGscLoading] = useState(false);

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

  async function loadGsc(period: string) {
    setGscLoading(true);
    try {
      const [perf, queries, pages] = await Promise.all([
        gscAPI.getPerformance(period),
        gscAPI.getQueries(period),
        gscAPI.getPages(period),
      ]);
      setGscPerf(perf);
      setGscQueries(queries.queries);
      setGscPages(pages.pages);
    } catch (e) {
      console.error("Failed to load GSC data:", e);
    } finally {
      setGscLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    // Check GSC status
    gscAPI.getStatus().then((status) => {
      setGscStatus(status);
      if (status.connected && status.selected_site) {
        loadGsc("28d");
      }
    }).catch(() => {});
  }, []);

  function handleGscPeriodChange(period: string) {
    setGscPeriod(period);
    loadGsc(period);
  }

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

  // Build competitor list for ranking grid
  const competitorNames: string[] = [];
  if (insights) {
    const nameSet = new Set<string>();
    insights.share_of_voice.forEach(s => nameSet.add(s.competitor));
    competitorNames.push(...Array.from(nameSet));
  }

  const gscConnected = gscStatus?.connected && gscStatus?.selected_site;

  // Sparkline-like simple bar chart for daily data
  const maxClicks = gscPerf ? Math.max(...gscPerf.daily.map(d => d.clicks), 1) : 1;

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
          {tracking ? "Tracking en cours..." : "Tracker les positions"}
        </button>
      </div>

      {/* Track result banner */}
      {trackResult && (
        <div className="rounded-xl bg-blue-50 border border-blue-200 px-4 py-3 text-sm text-blue-700">
          {trackResult}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* GSC Section: Mon site                                              */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {gscConnected ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
              <MousePointerClick className="h-5 w-5 text-emerald-500" />
              Mon site (Google Search Console)
            </h2>
            <div className="flex items-center gap-2">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => handleGscPeriodChange(opt.value)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    gscPeriod === opt.value
                      ? "bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {gscLoading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-5 w-5 animate-spin text-emerald-500" />
              <span className="ml-3 text-sm text-muted-foreground">Chargement des donnees GSC...</span>
            </div>
          ) : gscPerf ? (
            <>
              {/* GSC KPIs */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <KpiCard label="Clics" value={formatNumber(gscPerf.total_clicks)} icon={MousePointerClick} color="emerald" />
                <KpiCard label="Impressions" value={formatNumber(gscPerf.total_impressions)} icon={Eye} color="blue" />
                <KpiCard label="CTR moyen" value={`${gscPerf.avg_ctr}%`} icon={TrendingUp} color="violet" />
                <KpiCard label="Position moy." value={gscPerf.avg_position.toFixed(1)} icon={Search} color="amber" />
              </div>

              {/* Daily chart */}
              <div className="rounded-2xl border border-border bg-card p-6">
                <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-emerald-500" />
                  Clics par jour
                </h3>
                <div className="flex items-end gap-[2px] h-32">
                  {gscPerf.daily.map((d) => (
                    <div key={d.date} className="flex-1 flex flex-col items-center group relative">
                      <div
                        className="w-full bg-gradient-to-t from-emerald-500 to-emerald-400 rounded-t-sm transition-all hover:from-emerald-600 hover:to-emerald-500 min-h-[2px]"
                        style={{ height: `${(d.clicks / maxClicks) * 100}%` }}
                      />
                      <div className="absolute -top-8 left-1/2 -translate-x-1/2 hidden group-hover:block z-10 whitespace-nowrap rounded bg-gray-900 text-white text-[10px] px-2 py-1 shadow">
                        {d.date}: {d.clicks} clics
                      </div>
                    </div>
                  ))}
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-[10px] text-muted-foreground">{gscPerf.daily[0]?.date}</span>
                  <span className="text-[10px] text-muted-foreground">{gscPerf.daily[gscPerf.daily.length - 1]?.date}</span>
                </div>
              </div>

              {/* Top queries table */}
              {gscQueries.length > 0 && (
                <div className="rounded-2xl border border-border bg-card p-6 overflow-x-auto">
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Search className="h-4 w-4 text-emerald-500" />
                    Top requetes ({gscQueries.length})
                  </h3>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Requete</th>
                        <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Clics</th>
                        <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Impr.</th>
                        <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">CTR</th>
                        <th className="text-right py-2 pl-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Position</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gscQueries.map((q, i) => (
                        <tr key={q.query} className="border-b border-border/50 hover:bg-muted/30">
                          <td className="py-2.5 pr-4">
                            <span className="text-muted-foreground mr-2 text-xs">{i + 1}.</span>
                            <span className="font-medium text-foreground">{q.query}</span>
                          </td>
                          <td className="text-right py-2.5 px-3 font-semibold text-emerald-600">{formatNumber(q.clicks)}</td>
                          <td className="text-right py-2.5 px-3 text-muted-foreground">{formatNumber(q.impressions)}</td>
                          <td className="text-right py-2.5 px-3 text-muted-foreground">{q.ctr}%</td>
                          <td className="text-right py-2.5 pl-3">
                            <PositionBadge position={Math.round(q.position)} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Top pages table */}
              {gscPages.length > 0 && (
                <div className="rounded-2xl border border-border bg-card p-6 overflow-x-auto">
                  <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                    <Globe className="h-4 w-4 text-emerald-500" />
                    Top pages ({gscPages.length})
                  </h3>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Page</th>
                        <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Clics</th>
                        <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Impr.</th>
                        <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">CTR</th>
                        <th className="text-right py-2 pl-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Position</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gscPages.map((p, i) => {
                        let shortPage = p.page;
                        try {
                          const u = new URL(p.page);
                          shortPage = u.pathname === "/" ? u.hostname : u.pathname;
                        } catch {}
                        return (
                          <tr key={p.page} className="border-b border-border/50 hover:bg-muted/30">
                            <td className="py-2.5 pr-4">
                              <span className="text-muted-foreground mr-2 text-xs">{i + 1}.</span>
                              <a href={p.page} target="_blank" rel="noopener noreferrer" className="font-medium text-blue-600 hover:underline truncate inline-block max-w-sm">
                                {shortPage}
                              </a>
                            </td>
                            <td className="text-right py-2.5 px-3 font-semibold text-emerald-600">{formatNumber(p.clicks)}</td>
                            <td className="text-right py-2.5 px-3 text-muted-foreground">{formatNumber(p.impressions)}</td>
                            <td className="text-right py-2.5 px-3 text-muted-foreground">{p.ctr}%</td>
                            <td className="text-right py-2.5 pl-3">
                              <PositionBadge position={Math.round(p.position)} />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : null}
        </div>
      ) : (
        /* GSC not connected banner */
        <div className="rounded-2xl border border-emerald-200 bg-gradient-to-r from-emerald-50 to-teal-50 p-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100">
              <MousePointerClick className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-emerald-800">Google Search Console</p>
              <p className="text-xs text-emerald-600">
                Connectez GSC pour voir les vrais clics, impressions et positions de votre site
              </p>
            </div>
          </div>
          <Link
            href="/account"
            className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
          >
            <PlugZap className="h-4 w-4" />
            Connecter
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* SERP Section: Concurrents                                          */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {gscConnected && (
        <div className="pt-2">
          <h2 className="text-lg font-bold text-foreground flex items-center gap-2 mb-4">
            <Search className="h-5 w-5 text-blue-500" />
            Concurrents (SERP)
          </h2>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin text-blue-500" />
          <span className="ml-3 text-muted-foreground">Chargement des donnees SEO...</span>
        </div>
      ) : !insights || insights.total_keywords === 0 ? (
        <div className="rounded-2xl border border-dashed border-blue-300 bg-blue-50/50 p-12 text-center">
          <Search className="h-12 w-12 text-blue-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">Aucune donnee SEO</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Cliquez sur &quot;Tracker les positions&quot; pour lancer le premier scan des resultats Google.
          </p>
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
              {insights.share_of_voice.map((s) => {
                const isBrand = s.competitor_id === brandId;
                return (
                  <div key={s.competitor_id} className="flex items-center gap-3">
                    <span className={`w-28 text-sm font-medium truncate ${isBrand ? "text-blue-700 font-bold" : "text-foreground"}`}>
                      {s.competitor}
                    </span>
                    <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${isBrand ? "bg-gradient-to-r from-blue-500 to-indigo-500" : "bg-gray-300"}`}
                        style={{ width: `${Math.max(s.pct, 2)}%` }}
                      />
                    </div>
                    <span className={`text-sm font-semibold w-16 text-right ${isBrand ? "text-blue-700" : "text-muted-foreground"}`}>
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
                return (
                  <div key={a.competitor_id} className={`rounded-xl p-4 ${isBrand ? "bg-blue-50 border border-blue-200" : "bg-gray-50 border border-gray-200"}`}>
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-sm font-semibold ${isBrand ? "text-blue-700" : "text-foreground"}`}>
                        #{i + 1} {a.competitor}
                      </span>
                    </div>
                    <div className={`text-2xl font-bold ${isBrand ? "text-blue-600" : "text-foreground"}`}>
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

          {/* Recommendations */}
          {insights.recommendations.length > 0 && (
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
    blue: "from-blue-500 to-blue-600 shadow-blue-200/50",
    indigo: "from-indigo-500 to-indigo-600 shadow-indigo-200/50",
    violet: "from-violet-500 to-violet-600 shadow-violet-200/50",
    sky: "from-sky-500 to-sky-600 shadow-sky-200/50",
    emerald: "from-emerald-500 to-emerald-600 shadow-emerald-200/50",
    amber: "from-amber-500 to-amber-600 shadow-amber-200/50",
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br ${colors[color] || colors.blue} shadow-md`}>
          <Icon className="h-3.5 w-3.5 text-white" />
        </div>
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
      </div>
      <p className="text-lg font-bold text-foreground">{value}</p>
      {subtitle && <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>}
    </div>
  );
}
