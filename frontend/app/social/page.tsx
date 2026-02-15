"use client";

import React, { useEffect, useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  competitorsAPI,
  instagramAPI,
  tiktokAPI,
  youtubeAPI,
  brandAPI,
  socialContentAPI,
  CompetitorListItem,
  ContentInsights,
} from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import {
  RefreshCw,
  ExternalLink,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Users,
  BarChart3,
  Zap,
  Trophy,
  Target,
  Heart,
  Crown,
  Brain,
  Sparkles,
  Hash,
  Play,
  Eye,
  Clock,
  Calendar,
  Instagram,
  Music,
  Youtube,
  Layers,
} from "lucide-react";
import { PeriodFilter, PeriodDays, periodLabel } from "@/components/period-filter";

type Platform = "instagram" | "tiktok" | "youtube";
type RankingView = "audience" | "engagement" | "growth" | "efficiency";

const PLATFORM_CONFIG = {
  instagram: {
    label: "Instagram",
    gradient: "from-pink-500 via-purple-500 to-orange-400",
    darkBg: "from-pink-950 via-purple-950 to-orange-950",
    accent: "text-pink-500",
    dot: "bg-pink-500",
    lightBg: "bg-pink-50 dark:bg-pink-950/30",
    border: "border-pink-200 dark:border-pink-900",
    link: (username: string) => `https://instagram.com/${username}`,
    linkLabel: (username: string) => `@${username}`,
  },
  tiktok: {
    label: "TikTok",
    gradient: "from-cyan-400 via-slate-900 to-pink-500",
    darkBg: "from-slate-950 via-slate-900 to-slate-950",
    accent: "text-cyan-400",
    dot: "bg-slate-800",
    lightBg: "bg-slate-50 dark:bg-slate-900/50",
    border: "border-slate-200 dark:border-slate-800",
    link: (username: string) => `https://tiktok.com/@${username}`,
    linkLabel: (username: string) => `@${username}`,
  },
  youtube: {
    label: "YouTube",
    gradient: "from-red-600 via-red-500 to-red-700",
    darkBg: "from-red-950 via-red-900 to-red-950",
    accent: "text-red-500",
    dot: "bg-red-500",
    lightBg: "bg-red-50 dark:bg-red-950/30",
    border: "border-red-200 dark:border-red-900",
    link: (channelId: string) => `https://youtube.com/channel/${channelId}`,
    linkLabel: () => "YouTube",
  },
};

const RANKING_VIEWS_BASE: { key: RankingView; label: string; icon: React.ReactNode }[] = [
  { key: "audience", label: "Audience", icon: <Users className="h-3 w-3" /> },
  { key: "engagement", label: "Engagement", icon: <Target className="h-3 w-3" /> },
  { key: "growth", label: "Croissance", icon: <TrendingUp className="h-3 w-3" /> },
  { key: "efficiency", label: "Efficacite", icon: <Zap className="h-3 w-3" /> },
];

function GrowthBadge({ value }: { value?: number }) {
  if (value === undefined || value === null) return <span className="text-xs text-muted-foreground">&mdash;</span>;
  const isPositive = value > 0;
  const isNegative = value < 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums ${
        isPositive ? "text-emerald-600" : isNegative ? "text-red-500" : "text-muted-foreground"
      }`}
    >
      {isPositive ? <TrendingUp className="h-3 w-3" /> : isNegative ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
      {isPositive ? "+" : ""}{value.toFixed(1)}%
    </span>
  );
}

const MEDAL = ["bg-amber-400 text-amber-950", "bg-slate-300 text-slate-700", "bg-orange-300 text-orange-800"];

export default function SocialPage() {
  const [platform, setPlatform] = useState<Platform>("instagram");
  const [rankingView, setRankingView] = useState<RankingView>("audience");
  const [periodDays, setPeriodDays] = useState<PeriodDays>(7);
  const [competitors, setCompetitors] = useState<CompetitorListItem[]>([]);
  const [igComparison, setIgComparison] = useState<any[]>([]);
  const [ttComparison, setTtComparison] = useState<any[]>([]);
  const [ytComparison, setYtComparison] = useState<any[]>([]);
  const [brandName, setBrandName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);

  const [contentInsights, setContentInsights] = useState<ContentInsights | null>(null);
  const [contentLoading, setContentLoading] = useState(false);
  const [contentStatus, setContentStatus] = useState<string | null>(null);
  const [initialLoad, setInitialLoad] = useState(true);
  const [contentPlatform, setContentPlatform] = useState<string | null>(null); // null = overview (all)

  useEffect(() => {
    async function loadAll() {
      try {
        const [comp, ig, tt, yt, brand, ci] = await Promise.allSettled([
          competitorsAPI.list(),
          instagramAPI.getComparison(periodDays),
          tiktokAPI.getComparison(periodDays),
          youtubeAPI.getComparison(periodDays),
          brandAPI.getProfile(),
          socialContentAPI.getInsights(contentPlatform || undefined),
        ]);
        if (comp.status === "fulfilled") setCompetitors(comp.value);
        if (ig.status === "fulfilled") setIgComparison(ig.value);
        if (tt.status === "fulfilled") setTtComparison(tt.value);
        if (yt.status === "fulfilled") setYtComparison(yt.value);
        if (brand.status === "fulfilled") setBrandName((brand.value as any).company_name || null);
        if (ci.status === "fulfilled") setContentInsights(ci.value);
      } catch (err) {
        console.error("Failed to load:", err);
      } finally {
        if (initialLoad) { setLoading(false); setInitialLoad(false); }
      }
    }
    loadAll();
  }, [periodDays, contentPlatform]);

  // Auto-trigger content analysis once if no data
  const autoAnalyzedRef = React.useRef(false);
  useEffect(() => {
    if (!loading && !autoAnalyzedRef.current && contentInsights && contentInsights.total_analyzed === 0) {
      autoAnalyzedRef.current = true;
      handleAnalyzeContent();
    }
  }, [loading, contentInsights]);

  async function handleRefreshAll() {
    setFetching(true);
    try {
      const relevantCompetitors = competitors.filter((c) => {
        if (platform === "instagram") return c.active_channels.includes("instagram");
        if (platform === "tiktok") return c.active_channels.includes("tiktok");
        if (platform === "youtube") return c.active_channels.includes("youtube");
        return false;
      });
      for (const c of relevantCompetitors) {
        try {
          if (platform === "instagram") await instagramAPI.fetch(c.id);
          if (platform === "tiktok") await tiktokAPI.fetch(c.id);
          if (platform === "youtube") await youtubeAPI.fetch(c.id);
        } catch {}
      }
      const [ig, tt, yt] = await Promise.allSettled([
        instagramAPI.getComparison(periodDays),
        tiktokAPI.getComparison(periodDays),
        youtubeAPI.getComparison(periodDays),
      ]);
      if (ig.status === "fulfilled") setIgComparison(ig.value);
      if (tt.status === "fulfilled") setTtComparison(tt.value);
      if (yt.status === "fulfilled") setYtComparison(yt.value);
    } catch (err) {
      console.error("Refresh failed:", err);
    } finally {
      setFetching(false);
    }
  }

  async function handleAnalyzeContent() {
    setContentLoading(true);
    setContentStatus(null);
    try {
      // Step 1: Collect
      setContentStatus("Collecte des posts sociaux en cours...");
      const collectResult = await socialContentAPI.collectAll();

      // Build detailed status
      const details: string[] = [];
      if (collectResult.by_competitor && collectResult.by_competitor.length > 0) {
        const hasContent = collectResult.by_competitor.some(
          (c: any) => (c.tiktok || 0) + (c.youtube || 0) + (c.instagram || 0) > 0
        );
        if (hasContent) {
          for (const c of collectResult.by_competitor) {
            const parts = [];
            if (c.tiktok) parts.push(`${c.tiktok} TikTok`);
            if (c.youtube) parts.push(`${c.youtube} YouTube`);
            if (c.instagram) parts.push(`${c.instagram} Instagram`);
            if (parts.length > 0) details.push(`${c.competitor}: ${parts.join(", ")}`);
          }
        }
      }

      const errCount = collectResult.errors?.length || 0;
      const scanned = collectResult.competitors_scanned || 0;
      const collectMsg = collectResult.new > 0
        ? `${collectResult.new} nouveaux posts collectes${collectResult.updated ? `, ${collectResult.updated} mis a jour` : ""} (${scanned} concurrents scannes). Analyse IA en cours...`
        : collectResult.total_in_db > 0
          ? `Aucun nouveau post (${collectResult.total_in_db} en base, ${scanned} concurrents scannes). Analyse IA en cours...`
          : scanned > 0
            ? `Aucun post collecte sur ${scanned} concurrents scannes.${errCount > 0 ? ` ${errCount} erreur(s) API.` : " Verifiez les comptes sociaux de vos concurrents."}`
            : `Aucun concurrent trouve. Ajoutez des concurrents dans "Mon enseigne".`;
      setContentStatus(details.length > 0 ? `${collectMsg}\n${details.join(" | ")}` : collectMsg);

      // Step 2: Analyze in batches (auto-continues until done)
      if (collectResult.total_in_db > 0 || collectResult.new > 0) {
        let totalAnalyzed = 0;
        let totalErrors = 0;
        let batchNum = 0;
        const MAX_BATCHES = 10; // Safety limit: max 10 batches per click

        while (batchNum < MAX_BATCHES) {
          batchNum++;
          const analyzeResult = await socialContentAPI.analyzeAll(10);
          totalAnalyzed += analyzeResult.analyzed || 0;
          totalErrors += analyzeResult.errors || 0;

          if (analyzeResult.analyzed > 0) {
            setContentStatus(
              `Analyse IA: ${totalAnalyzed} posts analyses${totalErrors > 0 ? `, ${totalErrors} erreurs` : ""}${analyzeResult.remaining > 0 ? ` — ${analyzeResult.remaining} restants...` : ""}`
            );
          }

          // Stop if nothing left or no progress this batch
          if (analyzeResult.remaining === 0 || analyzeResult.analyzed === 0) break;
        }

        if (totalAnalyzed === 0) {
          setContentStatus("Tous les posts sont deja analyses.");
        }
      }

      // Step 3: Refresh insights
      const insights = await socialContentAPI.getInsights(contentPlatform || undefined);
      setContentInsights(insights);
    } catch (err: any) {
      console.error("Content analysis failed:", err);
      setContentStatus(`Erreur: ${err.message || "Echec de l'analyse"}`);
    } finally {
      setContentLoading(false);
    }
  }

  const isBrand = (name: string) => brandName && name.toLowerCase() === brandName.toLowerCase();

  // Cross-platform overview
  const crossPlatformData = useMemo(() => {
    const competitorMap = new Map<number, { id: number; name: string; ig: any; tt: any; yt: any }>();
    igComparison.forEach(c => {
      if (!competitorMap.has(c.competitor_id)) competitorMap.set(c.competitor_id, { id: c.competitor_id, name: c.competitor_name, ig: null, tt: null, yt: null });
      competitorMap.get(c.competitor_id)!.ig = c;
    });
    ttComparison.forEach(c => {
      if (!competitorMap.has(c.competitor_id)) competitorMap.set(c.competitor_id, { id: c.competitor_id, name: c.competitor_name, ig: null, tt: null, yt: null });
      competitorMap.get(c.competitor_id)!.tt = c;
    });
    ytComparison.forEach(c => {
      if (!competitorMap.has(c.competitor_id)) competitorMap.set(c.competitor_id, { id: c.competitor_id, name: c.competitor_name, ig: null, tt: null, yt: null });
      competitorMap.get(c.competitor_id)!.yt = c;
    });
    return Array.from(competitorMap.values())
      .map(c => ({
        ...c,
        totalReach: (c.ig?.followers || 0) + (c.tt?.followers || 0) + (c.yt?.subscribers || 0),
        avgGrowth: (() => {
          const growths: number[] = [];
          if (c.ig?.follower_growth_7d != null) growths.push(c.ig.follower_growth_7d);
          if (c.tt?.follower_growth_7d != null) growths.push(c.tt.follower_growth_7d);
          if (c.yt?.subscriber_growth_7d != null) growths.push(c.yt.subscriber_growth_7d);
          return growths.length > 0 ? growths.reduce((a, b) => a + b, 0) / growths.length : 0;
        })(),
        platformCount: (c.ig ? 1 : 0) + (c.tt ? 1 : 0) + (c.yt ? 1 : 0),
      }))
      .sort((a, b) => b.totalReach - a.totalReach);
  }, [igComparison, ttComparison, ytComparison]);

  // Current platform data
  const currentData = platform === "instagram" ? igComparison : platform === "tiktok" ? ttComparison : ytComparison;
  const config = PLATFORM_CONFIG[platform];

  // Get ranking metric
  function getRankingValue(c: any): number {
    if (rankingView === "audience") return platform === "youtube" ? (c.subscribers || 0) : (c.followers || 0);
    if (rankingView === "engagement") {
      if (platform === "instagram") return c.engagement_rate || 0;
      if (platform === "tiktok") return c.videos_count > 0 ? (c.likes || 0) / c.videos_count : 0;
      return c.engagement_rate || 0;
    }
    if (rankingView === "growth") return c.follower_growth_7d ?? c.subscriber_growth_7d ?? 0;
    if (rankingView === "efficiency") {
      if (platform === "instagram") return c.avg_likes || 0;
      if (platform === "tiktok") return c.videos_count > 0 ? (c.likes || 0) / c.videos_count : 0;
      return c.avg_views || 0;
    }
    return 0;
  }

  function getRankingLabel(): string {
    if (rankingView === "audience") return platform === "youtube" ? "abonnes" : "followers";
    if (rankingView === "engagement") return platform === "tiktok" ? "likes/video" : "engagement";
    if (rankingView === "growth") return "croissance 7j";
    if (rankingView === "efficiency") {
      if (platform === "instagram") return "likes moy/post";
      if (platform === "tiktok") return "likes/video";
      return "vues moy";
    }
    return "";
  }

  function formatRankingValue(val: number): string {
    if (rankingView === "engagement") return platform === "tiktok" ? formatNumber(Math.round(val)) : `${val.toFixed(2)}%`;
    if (rankingView === "growth") return `${val > 0 ? "+" : ""}${val.toFixed(1)}%`;
    return formatNumber(Math.round(val));
  }

  const sorted = [...currentData].sort((a, b) => getRankingValue(b) - getRankingValue(a));
  const maxRankingVal = sorted.length > 0 ? getRankingValue(sorted[0]) || 1 : 1;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement des r&eacute;seaux sociaux...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
            <Activity className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">R&eacute;seaux sociaux</h1>
            <p className="text-[13px] text-muted-foreground">Comparaison multi-plateformes</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <PeriodFilter selectedDays={periodDays} onDaysChange={setPeriodDays} />
          <Button variant="outline" size="sm" onClick={handleRefreshAll} disabled={fetching} className="gap-2">
            <RefreshCw className={`h-3.5 w-3.5 ${fetching ? "animate-spin" : ""}`} />
            Rafra&icirc;chir
          </Button>
        </div>
      </div>

      {/* ── Cross-Platform Overview ── */}
      {crossPlatformData.length > 0 && (
        <div className="rounded-2xl bg-gradient-to-br from-indigo-950 via-[#1e1b4b] to-violet-950 text-white p-5 sm:p-6 space-y-4 overflow-hidden">
          <div className="flex items-center gap-2.5">
            <Crown className="h-4.5 w-4.5 text-amber-400" />
            <h2 className="text-sm font-semibold">Vue d&apos;ensemble multi-plateformes</h2>
          </div>
          <div className="overflow-x-auto -mx-5 sm:-mx-6 px-5 sm:px-6">
            <table className="w-full min-w-[600px]">
              <thead>
                <tr className="text-[10px] uppercase tracking-widest text-white/40">
                  <th className="text-left pb-3 font-semibold">#</th>
                  <th className="text-left pb-3 font-semibold">Concurrent</th>
                  <th className="text-right pb-3 font-semibold">Instagram</th>
                  <th className="text-right pb-3 font-semibold">TikTok</th>
                  <th className="text-right pb-3 font-semibold">YouTube</th>
                  <th className="text-right pb-3 font-semibold">Audience totale</th>
                  <th className="text-right pb-3 font-semibold">Tendance 7j</th>
                </tr>
              </thead>
              <tbody>
                {crossPlatformData.map((c, i) => (
                  <tr key={c.id} className={`border-t border-white/10 ${isBrand(c.name) ? "bg-violet-500/15" : ""}`}>
                    <td className="py-2.5 pr-2">
                      {i < 3 ? (
                        <span className={`inline-flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold ${MEDAL[i]}`}>{i + 1}</span>
                      ) : (
                        <span className="text-xs text-white/40 tabular-nums pl-1">{i + 1}</span>
                      )}
                    </td>
                    <td className="py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{c.name}</span>
                        {isBrand(c.name) && (
                          <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-violet-500/30 text-violet-300">Vous</span>
                        )}
                      </div>
                    </td>
                    <td className="py-2.5 text-right text-sm tabular-nums">
                      {c.ig ? <span className="text-pink-300">{formatNumber(c.ig.followers)}</span> : <span className="text-white/20">&mdash;</span>}
                    </td>
                    <td className="py-2.5 text-right text-sm tabular-nums">
                      {c.tt ? <span className="text-cyan-300">{formatNumber(c.tt.followers)}</span> : <span className="text-white/20">&mdash;</span>}
                    </td>
                    <td className="py-2.5 text-right text-sm tabular-nums">
                      {c.yt ? <span className="text-red-300">{formatNumber(c.yt.subscribers)}</span> : <span className="text-white/20">&mdash;</span>}
                    </td>
                    <td className="py-2.5 text-right">
                      <span className="text-sm font-bold tabular-nums">{formatNumber(c.totalReach)}</span>
                    </td>
                    <td className="py-2.5 text-right">
                      <GrowthBadge value={c.avgGrowth} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Platform selector */}
      <div className="flex items-center gap-1 p-1 rounded-full bg-card border border-border w-fit">
        {(["instagram", "tiktok", "youtube"] as Platform[]).map((p) => {
          const pConfig = PLATFORM_CONFIG[p];
          const pData = p === "instagram" ? igComparison : p === "tiktok" ? ttComparison : ytComparison;
          const isActive = platform === p;
          return (
            <button
              key={p}
              onClick={() => { setPlatform(p); setRankingView("audience"); }}
              className={`relative px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
                isActive ? "text-white shadow-lg" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {isActive && <div className={`absolute inset-0 rounded-full bg-gradient-to-r ${pConfig.gradient}`} />}
              <span className="relative flex items-center gap-2">
                {pConfig.label}
                {pData.length > 0 && (
                  <span className={`text-[10px] tabular-nums ${isActive ? "text-white/70" : "text-muted-foreground"}`}>
                    {pData.length}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>

      {/* Content */}
      {currentData.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-card/50 p-12 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50">
              <Activity className="h-7 w-7 text-violet-400" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-1">Aucune donn&eacute;e {config.label}</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">Configurez des concurrents avec un compte {config.label}.</p>
        </div>
      ) : (
        <div className="space-y-6">

          {/* ── Ranking View Selector ── */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] text-muted-foreground uppercase tracking-widest font-semibold mr-1">Classer par</span>
            {RANKING_VIEWS_BASE.map(rv => (
              <button
                key={rv.key}
                onClick={() => setRankingView(rv.key)}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-all ${
                  rankingView === rv.key
                    ? `bg-gradient-to-r ${config.gradient} text-white border-transparent shadow-sm`
                    : "bg-card text-muted-foreground hover:text-foreground border-border hover:border-foreground/20"
                }`}
              >
                {rv.icon}{rv.label}
              </button>
            ))}
          </div>

          {/* ── Ranked Cards Grid ── */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {sorted.map((c, i) => {
              const primaryVal = getRankingValue(c);
              const pct = maxRankingVal > 0 ? (primaryVal / maxRankingVal) * 100 : 0;
              const followers = platform === "youtube" ? (c.subscribers || 0) : (c.followers || 0);
              const name = platform === "youtube" ? (c.channel_name || c.competitor_name) : c.competitor_name;
              const growth = c.follower_growth_7d ?? c.subscriber_growth_7d;
              const brand = isBrand(c.competitor_name);

              return (
                <div
                  key={c.competitor_id}
                  className={`rounded-xl border p-4 transition-all hover:shadow-md ${
                    brand ? "ring-2 ring-violet-500/40 bg-violet-50/30 dark:bg-violet-950/20" :
                    i === 0 ? `${config.lightBg} ${config.border}` : "bg-card"
                  }`}
                >
                  {/* Header: rank + name */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className={`flex items-center justify-center h-6 w-6 rounded-full text-[10px] font-bold shrink-0 ${
                        i < 3 ? MEDAL[i] : "bg-muted text-muted-foreground"
                      }`}>
                        {i + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-sm font-semibold truncate">{name}</span>
                          {brand && <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 shrink-0">Vous</span>}
                        </div>
                        {(c.username || c.channel_id) && (
                          <a href={config.link(c.username || c.channel_id)} target="_blank" rel="noopener noreferrer"
                            className={`text-[11px] ${config.accent} hover:underline flex items-center gap-0.5`}>
                            {config.linkLabel(c.username || c.channel_id)}
                            <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        )}
                      </div>
                    </div>
                    <GrowthBadge value={growth} />
                  </div>

                  {/* Primary metric */}
                  <div className="mb-2">
                    <div className="text-2xl font-bold tabular-nums">{formatRankingValue(primaryVal)}</div>
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest">{getRankingLabel()}</div>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden mb-3">
                    <div className={`h-full rounded-full transition-all duration-700 ${i === 0 ? `bg-gradient-to-r ${config.gradient}` : "bg-slate-300 dark:bg-slate-600"}`}
                      style={{ width: `${pct}%` }} />
                  </div>

                  {/* Secondary metrics */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {rankingView !== "audience" && (
                      <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                        <Users className="h-3 w-3" />{formatNumber(followers)}
                      </span>
                    )}
                    {platform === "instagram" && (
                      <>
                        {rankingView !== "engagement" && (
                          <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                            <Target className="h-3 w-3" />{c.engagement_rate?.toFixed(2) || "0"}%
                          </span>
                        )}
                        {rankingView !== "efficiency" && c.avg_likes != null && (
                          <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                            <Heart className="h-3 w-3" />{formatNumber(Math.round(c.avg_likes))} moy
                          </span>
                        )}
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.posts_count || 0)} posts
                        </span>
                      </>
                    )}
                    {platform === "tiktok" && (
                      <>
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                          <Heart className="h-3 w-3" />{formatNumber(c.likes || 0)}
                        </span>
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.videos_count || 0)} videos
                        </span>
                        {c.videos_count > 0 && rankingView !== "efficiency" && (
                          <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                            <Zap className="h-3 w-3" />{formatNumber(Math.round(c.likes / c.videos_count))}/vid
                          </span>
                        )}
                      </>
                    )}
                    {platform === "youtube" && (
                      <>
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.total_views || 0)} vues
                        </span>
                        <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.videos_count || 0)} videos
                        </span>
                        {rankingView !== "engagement" && (
                          <span className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
                            <Target className="h-3 w-3" />{c.engagement_rate?.toFixed(2) || "0"}%
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* ── Detailed Table ── */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-5 py-3 border-b bg-muted/20 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100">
                <BarChart3 className="h-3.5 w-3.5 text-slate-600" />
              </div>
              <span className="text-[12px] font-semibold text-foreground">D&eacute;tails complets</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[650px]">
                <thead>
                  <tr className="bg-muted/30">
                    <th className="text-left text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Concurrent</th>
                    <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">{platform === "youtube" ? "Abonnes" : "Followers"}</th>
                    {platform === "instagram" && (
                      <>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Engagement</th>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Likes moy</th>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Posts</th>
                      </>
                    )}
                    {platform === "tiktok" && (
                      <>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Likes</th>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Videos</th>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Likes/vid</th>
                      </>
                    )}
                    {platform === "youtube" && (
                      <>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Vues totales</th>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Vues moy</th>
                        <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">Engagement</th>
                      </>
                    )}
                    <th className="text-right text-[10px] uppercase tracking-widest text-muted-foreground font-semibold px-4 py-2.5">7j</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((c, i) => {
                    const val = platform === "youtube" ? (c.subscribers || 0) : (c.followers || 0);
                    const brand = isBrand(c.competitor_name);
                    return (
                      <tr key={c.competitor_id} className={`border-t transition-colors hover:bg-muted/30 ${brand ? "bg-violet-50/50 dark:bg-violet-950/20" : i === 0 ? config.lightBg : ""}`}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className={`flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold ${i < 3 ? MEDAL[i] : "bg-muted text-muted-foreground"}`}>{i + 1}</span>
                            <div>
                              <div className="flex items-center gap-1.5">
                                <span className="text-sm font-medium">{platform === "youtube" ? (c.channel_name || c.competitor_name) : c.competitor_name}</span>
                                {brand && <span className="text-[8px] font-bold uppercase px-1 py-0.5 rounded bg-violet-100 text-violet-700">Vous</span>}
                              </div>
                              {(c.username || c.channel_id) && (
                                <a href={config.link(c.username || c.channel_id)} target="_blank" rel="noopener noreferrer" className={`text-[11px] ${config.accent} hover:underline`}>
                                  {config.linkLabel(c.username || c.channel_id)}
                                </a>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right text-sm font-bold tabular-nums">{formatNumber(val)}</td>
                        {platform === "instagram" && (
                          <>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{c.engagement_rate?.toFixed(2) || "0"}%</td>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{c.avg_likes != null ? formatNumber(Math.round(c.avg_likes)) : "\u2014"}</td>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{formatNumber(c.posts_count || 0)}</td>
                          </>
                        )}
                        {platform === "tiktok" && (
                          <>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{formatNumber(c.likes || 0)}</td>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{formatNumber(c.videos_count || 0)}</td>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{c.videos_count > 0 ? formatNumber(Math.round(c.likes / c.videos_count)) : "\u2014"}</td>
                          </>
                        )}
                        {platform === "youtube" && (
                          <>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{formatNumber(c.total_views || 0)}</td>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{c.avg_views ? formatNumber(c.avg_views) : "\u2014"}</td>
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{c.engagement_rate?.toFixed(2) || "0"}%</td>
                          </>
                        )}
                        <td className="px-4 py-3 text-right">
                          <GrowthBadge value={c.follower_growth_7d ?? c.subscriber_growth_7d} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Brand Position Insight ── */}
          {brandName && sorted.length > 1 && (() => {
            const brandIdx = sorted.findIndex(c => isBrand(c.competitor_name));
            if (brandIdx < 0) return null;
            const leaderVal = getRankingValue(sorted[0]);
            const brandVal = getRankingValue(sorted[brandIdx]);
            const gap = leaderVal > 0 ? Math.round(((leaderVal - brandVal) / leaderVal) * 100) : 0;
            if (brandIdx === 0) return (
              <div className="rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 p-4 flex items-center gap-3">
                <Trophy className="h-5 w-5 text-emerald-600 shrink-0" />
                <p className="text-sm text-emerald-800 dark:text-emerald-200">
                  <span className="font-semibold">{brandName}</span> est leader {config.label} en {getRankingLabel()}.
                </p>
              </div>
            );
            return (
              <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-4 flex items-center gap-3">
                <Trophy className="h-5 w-5 text-amber-600 shrink-0" />
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  <span className="font-semibold">{brandName}</span> est {brandIdx + 1}&egrave;me sur {sorted.length} en {getRankingLabel()}, {gap}% derriere le leader.
                </p>
              </div>
            );
          })()}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* Intelligence Contenu (AI-powered social content analysis)            */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <div className="space-y-5 pt-4 border-t border-border">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 border border-emerald-200/50">
              <Brain className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight text-foreground">Intelligence Contenu</h2>
              <p className="text-[13px] text-muted-foreground">Analyse IA des posts sociaux (themes, tons, hooks)</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleAnalyzeContent}
            disabled={contentLoading}
            className="gap-2 border-emerald-200 hover:bg-emerald-50 hover:text-emerald-700"
          >
            <Brain className={`h-3.5 w-3.5 ${contentLoading ? "animate-pulse" : ""}`} />
            {contentLoading ? "Analyse..." : "Rafraichir le contenu"}
          </Button>
        </div>

        {/* Content Platform Switcher */}
        <div className="flex items-center gap-1 p-1 rounded-full bg-card border border-border w-fit">
          {([
            { key: null, label: "Vue globale", icon: <Layers className="h-3 w-3" /> },
            { key: "instagram", label: "Instagram", icon: <Instagram className="h-3 w-3" /> },
            { key: "tiktok", label: "TikTok", icon: <Music className="h-3 w-3" /> },
            { key: "youtube", label: "YouTube", icon: <Youtube className="h-3 w-3" /> },
          ] as { key: string | null; label: string; icon: React.ReactNode }[]).map((p) => {
            const isActive = contentPlatform === p.key;
            return (
              <button
                key={p.key ?? "all"}
                onClick={() => setContentPlatform(p.key)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-medium transition-all ${
                  isActive
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                }`}
              >
                {p.icon}
                {p.label}
              </button>
            );
          })}
        </div>

        {/* Status */}
        {contentStatus && (
          <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 px-4 py-2.5 text-sm text-emerald-800 dark:text-emerald-200">
            {contentStatus}
          </div>
        )}

        {contentInsights && contentInsights.total_analyzed > 0 && (() => {
          // Pre-compute key engagement insights for hero cards
          const bestSlot = contentInsights.posting_timing?.best_slots?.[0];
          const bestDay = contentInsights.posting_frequency?.day_distribution
            ?.filter(d => d.count > 0)
            .sort((a, b) => b.count - a.count)[0];
          const bestTone = contentInsights.best_tone_engagement;

          return (
          <div className="space-y-5">
            {/* KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Score moyen", value: `${contentInsights.avg_score}/100`, icon: <Target className="h-4 w-4" /> },
                { label: "Posts analyses", value: String(contentInsights.total_analyzed), icon: <BarChart3 className="h-4 w-4" /> },
                { label: "Themes", value: String(contentInsights.themes.length), icon: <Hash className="h-4 w-4" /> },
                { label: "Plateformes", value: String(contentInsights.by_platform.length), icon: <Play className="h-4 w-4" /> },
              ].map((kpi) => (
                <div key={kpi.label} className="rounded-xl border bg-card p-4">
                  <div className="flex items-center gap-2 text-muted-foreground mb-1">
                    {kpi.icon}
                    <span className="text-[10px] uppercase tracking-widest font-semibold">{kpi.label}</span>
                  </div>
                  <div className="text-2xl font-bold text-foreground">{kpi.value}</div>
                </div>
              ))}
            </div>

            {/* ── KEY ENGAGEMENT INSIGHTS (hero cards) ── */}
            {(bestSlot || bestDay || bestTone) && (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Best time slot */}
                {bestSlot && (
                  <div className="rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white p-5 shadow-lg shadow-emerald-200/40">
                    <div className="flex items-center gap-2 mb-2">
                      <Clock className="h-5 w-5 text-emerald-100" />
                      <span className="text-[10px] uppercase tracking-widest font-bold text-emerald-100">Meilleur creneau</span>
                    </div>
                    <div className="text-2xl font-black">{bestSlot.label}</div>
                    <p className="text-emerald-100 text-xs mt-1">
                      {bestSlot.avg_engagement.toLocaleString("fr-FR")} interactions moy. sur {bestSlot.posts} posts
                    </p>
                  </div>
                )}

                {/* Best day */}
                {bestDay && (
                  <div className="rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white p-5 shadow-lg shadow-blue-200/40">
                    <div className="flex items-center gap-2 mb-2">
                      <Calendar className="h-5 w-5 text-blue-100" />
                      <span className="text-[10px] uppercase tracking-widest font-bold text-blue-100">Jour le plus actif</span>
                    </div>
                    <div className="text-2xl font-black">{bestDay.day}</div>
                    <p className="text-blue-100 text-xs mt-1">
                      {bestDay.count} publications ce jour
                    </p>
                  </div>
                )}

                {/* Best tone by engagement */}
                {bestTone && (
                  <div className="rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 text-white p-5 shadow-lg shadow-violet-200/40">
                    <div className="flex items-center gap-2 mb-2">
                      <Zap className="h-5 w-5 text-violet-100" />
                      <span className="text-[10px] uppercase tracking-widest font-bold text-violet-100">Ton le + engageant</span>
                    </div>
                    <div className="text-2xl font-black capitalize">{bestTone.tone}</div>
                    <p className="text-violet-100 text-xs mt-1">
                      Score moy. {bestTone.avg_score}/100 sur {bestTone.count} posts
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Insights Grid */}
            <div className="grid gap-4 md:grid-cols-2">
              {/* Themes dominants */}
              <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Hash className="h-4 w-4 text-emerald-500" />
                  Themes dominants
                </h3>
                <div className="space-y-2">
                  {contentInsights.themes.slice(0, 6).map((t) => (
                    <div key={t.theme} className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground w-24 truncate">{t.theme}</span>
                      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500"
                          style={{ width: `${t.pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold tabular-nums w-10 text-right">{t.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Tons utilises */}
              <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-teal-500" />
                  Tons utilises
                </h3>
                <div className="space-y-2">
                  {contentInsights.tones.slice(0, 6).map((t) => (
                    <div key={t.tone} className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground w-24 truncate">{t.tone}</span>
                      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-teal-400 to-cyan-500"
                          style={{ width: `${t.pct}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold tabular-nums w-10 text-right">{t.pct}%</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Top Hashtags */}
              <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Hash className="h-4 w-4 text-emerald-500" />
                  Top hashtags
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {contentInsights.top_hashtags.slice(0, 15).map((h) => (
                    <span
                      key={h.hashtag}
                      className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                    >
                      #{h.hashtag.replace(/^#/, "")}
                      <span className="text-emerald-400 text-[10px]">{h.count}</span>
                    </span>
                  ))}
                  {contentInsights.top_hashtags.length === 0 && (
                    <span className="text-xs text-muted-foreground">Aucun hashtag detecte</span>
                  )}
                </div>
              </div>

              {/* Score par concurrent */}
              <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-amber-500" />
                  Score par concurrent
                </h3>
                <div className="space-y-2">
                  {contentInsights.by_competitor.map((c, i) => (
                    <div key={c.competitor} className={`flex items-center gap-3 rounded-lg px-2 py-1.5 ${isBrand(c.competitor) ? "bg-emerald-50 dark:bg-emerald-950/20" : ""}`}>
                      <span className={`flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold shrink-0 ${
                        i < 3 ? MEDAL[i] : "bg-muted text-muted-foreground"
                      }`}>
                        {i + 1}
                      </span>
                      <span className="text-sm font-medium flex-1 truncate">{c.competitor}</span>
                      <span className="text-xs text-muted-foreground">{c.count} posts</span>
                      <span className="text-sm font-bold tabular-nums">{c.avg_score}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Posting Frequency */}
            {contentInsights.posting_frequency && contentInsights.posting_frequency.by_competitor.length > 0 && (
              <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-emerald-500" />
                  Frequence de publication
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {/* Per competitor frequency */}
                  <div className="space-y-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Par concurrent</span>
                    {contentInsights.posting_frequency.by_competitor.map((f) => (
                      <div key={f.competitor} className="flex items-center justify-between rounded-lg bg-muted/30 px-3 py-2">
                        <span className="text-sm font-medium truncate">{f.competitor}</span>
                        <div className="flex items-center gap-3 shrink-0">
                          <span className="text-xs text-muted-foreground">{f.avg_per_week}/sem</span>
                          <span className="text-sm font-bold tabular-nums text-emerald-600">{f.avg_per_month}/mois</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {/* Day of week distribution */}
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Jour de publication</span>
                    <div className="mt-2 space-y-1.5">
                      {contentInsights.posting_frequency.day_distribution.map((d) => {
                        const maxCount = Math.max(...contentInsights.posting_frequency!.day_distribution.map(x => x.count), 1);
                        return (
                          <div key={d.day} className="flex items-center gap-2">
                            <span className="text-xs font-medium w-16 text-muted-foreground">{d.day.slice(0, 3)}</span>
                            <div className="flex-1 h-4 bg-muted/50 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-emerald-400 rounded-full transition-all"
                                style={{ width: `${(d.count / maxCount) * 100}%` }}
                              />
                            </div>
                            <span className="text-xs font-bold tabular-nums w-6 text-right">{d.count}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Posting Timing */}
            {contentInsights.posting_timing && contentInsights.posting_timing.hour_distribution.some(h => h.count > 0) && (
              <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Clock className="h-4 w-4 text-emerald-500" />
                  Heures de publication & engagement
                </h3>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Hour distribution heatmap */}
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Volume par heure</span>
                    <div className="mt-2 flex items-end gap-[3px] h-24">
                      {contentInsights.posting_timing.hour_distribution.map((h) => {
                        const maxCount = Math.max(...contentInsights.posting_timing!.hour_distribution.map(x => x.count), 1);
                        const pct = (h.count / maxCount) * 100;
                        const maxEng = Math.max(...contentInsights.posting_timing!.hour_distribution.map(x => x.avg_engagement), 1);
                        const engRatio = h.avg_engagement / maxEng;
                        return (
                          <div key={h.hour} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                            <div
                              className={`w-full rounded-t transition-all ${engRatio > 0.7 ? "bg-emerald-500" : engRatio > 0.4 ? "bg-emerald-300" : "bg-gray-200"}`}
                              style={{ height: `${Math.max(pct, 3)}%` }}
                            />
                            <span className="text-[8px] text-muted-foreground mt-0.5">{h.hour % 6 === 0 ? h.label : ""}</span>
                            {/* Tooltip */}
                            <div className="absolute bottom-full mb-1 hidden group-hover:block z-10 bg-foreground text-background text-[10px] rounded px-2 py-1 whitespace-nowrap shadow-lg">
                              {h.label} — {h.count} posts, eng. moy. {h.avg_engagement.toLocaleString("fr-FR")}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-emerald-500" /> Fort engagement</span>
                      <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-emerald-300" /> Moyen</span>
                      <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-gray-200" /> Faible</span>
                    </div>
                  </div>

                  {/* Best slots */}
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Meilleurs creneaux (engagement)</span>
                    <div className="mt-2 space-y-1.5">
                      {contentInsights.posting_timing.best_slots.slice(0, 5).map((s, i) => (
                        <div key={i} className={`flex items-center gap-2 rounded-lg px-3 py-2 ${i === 0 ? "bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800" : "bg-muted/30"}`}>
                          <span className={`flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold shrink-0 ${
                            i === 0 ? "bg-emerald-500 text-white" : "bg-muted text-muted-foreground"
                          }`}>
                            {i + 1}
                          </span>
                          <span className={`text-sm font-medium flex-1 ${i === 0 ? "text-emerald-700 dark:text-emerald-300" : ""}`}>{s.label}</span>
                          <span className="text-xs text-muted-foreground">{s.posts} posts</span>
                          <span className="text-sm font-bold tabular-nums text-emerald-600">{s.avg_engagement.toLocaleString("fr-FR")}</span>
                        </div>
                      ))}
                    </div>
                    {/* Competitor peak hours */}
                    {contentInsights.posting_timing.competitor_peak_hours.length > 0 && (
                      <div className="mt-3 pt-3 border-t">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Heure de pointe par concurrent</span>
                        <div className="mt-1.5 flex flex-wrap gap-2">
                          {contentInsights.posting_timing.competitor_peak_hours.map((c) => (
                            <span key={c.competitor} className="inline-flex items-center gap-1.5 text-xs bg-muted/50 rounded-lg px-2.5 py-1.5">
                              <span className="font-medium">{c.competitor}</span>
                              <span className="font-bold text-emerald-600">{c.peak_label}</span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Top Performers */}
            {contentInsights.top_performers.length > 0 && (
              <div className="rounded-xl border bg-card p-5">
                <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-emerald-500" />
                  Top performers
                </h3>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {contentInsights.top_performers.slice(0, 6).map((p) => (
                    <div key={p.post_id} className="rounded-lg border bg-muted/20 p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-muted-foreground">{p.competitor_name}</span>
                        <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
                          {p.score}/100
                        </span>
                      </div>
                      {p.thumbnail_url && (
                        <div className="aspect-video rounded-md overflow-hidden bg-muted">
                          <img src={p.thumbnail_url} alt="" className="w-full h-full object-cover" />
                        </div>
                      )}
                      <p className="text-xs text-foreground line-clamp-2">{p.title || p.description}</p>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                          {p.platform}
                        </span>
                        {p.theme && (
                          <span className="inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/30 text-emerald-600">
                            {p.theme}
                          </span>
                        )}
                        <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground ml-auto">
                          <Eye className="h-3 w-3" />{formatNumber(p.views)}
                        </span>
                        <span className="inline-flex items-center gap-0.5 text-[10px] text-muted-foreground">
                          <Heart className="h-3 w-3" />{formatNumber(p.likes)}
                        </span>
                      </div>
                      {p.url && (
                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-emerald-600 hover:underline flex items-center gap-0.5">
                          Voir <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {contentInsights.recommendations.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-emerald-500" />
                  Recommandations strategiques
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {contentInsights.recommendations.map((rec, i) => (
                    <div
                      key={i}
                      className="rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 border border-emerald-200 dark:border-emerald-800 p-4 flex items-start gap-3"
                    >
                      <Sparkles className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                      <p className="text-sm text-emerald-900 dark:text-emerald-100">{rec}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          );
        })()}

        {/* Empty state — skeleton */}
        {(!contentInsights || contentInsights.total_analyzed === 0) && !contentLoading && (
          <div className="space-y-4 animate-pulse">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[1,2,3,4].map(i => (
                <div key={i} className="rounded-xl border bg-card p-4">
                  <div className="h-3 w-20 bg-emerald-100 rounded mb-3" />
                  <div className="h-7 w-14 bg-emerald-200 rounded" />
                </div>
              ))}
            </div>
            <div className="rounded-2xl border bg-card p-6">
              <div className="flex items-center gap-3 mb-4">
                <Brain className="h-5 w-5 animate-pulse text-emerald-500" />
                <span className="text-sm text-muted-foreground">Premiere analyse de contenu en cours...</span>
              </div>
              {[1,2,3].map(i => (
                <div key={i} className="h-10 bg-emerald-50 rounded-lg mb-2" />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
