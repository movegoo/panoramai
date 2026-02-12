"use client";

import { useEffect, useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  competitorsAPI,
  instagramAPI,
  tiktokAPI,
  youtubeAPI,
  brandAPI,
  CompetitorListItem,
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
} from "lucide-react";

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

const RANKING_VIEWS: { key: RankingView; label: string; icon: React.ReactNode }[] = [
  { key: "audience", label: "Audience", icon: <Users className="h-3 w-3" /> },
  { key: "engagement", label: "Engagement", icon: <Target className="h-3 w-3" /> },
  { key: "growth", label: "Croissance 7j", icon: <TrendingUp className="h-3 w-3" /> },
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
  const [competitors, setCompetitors] = useState<CompetitorListItem[]>([]);
  const [igComparison, setIgComparison] = useState<any[]>([]);
  const [ttComparison, setTtComparison] = useState<any[]>([]);
  const [ytComparison, setYtComparison] = useState<any[]>([]);
  const [brandName, setBrandName] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    async function loadAll() {
      try {
        const [comp, ig, tt, yt, brand] = await Promise.allSettled([
          competitorsAPI.list(),
          instagramAPI.getComparison(),
          tiktokAPI.getComparison(),
          youtubeAPI.getComparison(),
          brandAPI.getProfile(),
        ]);
        if (comp.status === "fulfilled") setCompetitors(comp.value);
        if (ig.status === "fulfilled") setIgComparison(ig.value);
        if (tt.status === "fulfilled") setTtComparison(tt.value);
        if (yt.status === "fulfilled") setYtComparison(yt.value);
        if (brand.status === "fulfilled") setBrandName((brand.value as any).company_name || null);
      } catch (err) {
        console.error("Failed to load:", err);
      } finally {
        setLoading(false);
      }
    }
    loadAll();
  }, []);

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
        instagramAPI.getComparison(),
        tiktokAPI.getComparison(),
        youtubeAPI.getComparison(),
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
        <Button variant="outline" size="sm" onClick={handleRefreshAll} disabled={fetching} className="gap-2">
          <RefreshCw className={`h-3.5 w-3.5 ${fetching ? "animate-spin" : ""}`} />
          Rafra&icirc;chir
        </Button>
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
            {RANKING_VIEWS.map(rv => (
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
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                        <Users className="h-2.5 w-2.5" />{formatNumber(followers)}
                      </span>
                    )}
                    {platform === "instagram" && (
                      <>
                        {rankingView !== "engagement" && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                            <Target className="h-2.5 w-2.5" />{c.engagement_rate?.toFixed(2) || "0"}%
                          </span>
                        )}
                        {rankingView !== "efficiency" && c.avg_likes != null && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                            <Heart className="h-2.5 w-2.5" />{formatNumber(c.avg_likes)} moy
                          </span>
                        )}
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.posts_count || 0)} posts
                        </span>
                      </>
                    )}
                    {platform === "tiktok" && (
                      <>
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          <Heart className="h-2.5 w-2.5" />{formatNumber(c.likes || 0)}
                        </span>
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.videos_count || 0)} videos
                        </span>
                        {c.videos_count > 0 && rankingView !== "efficiency" && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                            <Zap className="h-2.5 w-2.5" />{formatNumber(Math.round(c.likes / c.videos_count))}/vid
                          </span>
                        )}
                      </>
                    )}
                    {platform === "youtube" && (
                      <>
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.total_views || 0)} vues
                        </span>
                        <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                          {formatNumber(c.videos_count || 0)} videos
                        </span>
                        {rankingView !== "engagement" && (
                          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                            <Target className="h-2.5 w-2.5" />{c.engagement_rate?.toFixed(2) || "0"}%
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
                            <td className="px-4 py-3 text-right text-sm tabular-nums">{c.avg_likes != null ? formatNumber(c.avg_likes) : "\u2014"}</td>
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
    </div>
  );
}
