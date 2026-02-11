"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  competitorsAPI,
  instagramAPI,
  tiktokAPI,
  youtubeAPI,
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
} from "lucide-react";

type Platform = "instagram" | "tiktok" | "youtube";

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

function GrowthBadge({ value }: { value?: number }) {
  if (value === undefined || value === null) return <span className="text-xs text-muted-foreground">&mdash;</span>;
  const isPositive = value > 0;
  const isNegative = value < 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-semibold tabular-nums ${
        isPositive
          ? "text-emerald-600"
          : isNegative
          ? "text-red-500"
          : "text-muted-foreground"
      }`}
    >
      {isPositive ? (
        <TrendingUp className="h-3 w-3" />
      ) : isNegative ? (
        <TrendingDown className="h-3 w-3" />
      ) : (
        <Minus className="h-3 w-3" />
      )}
      {isPositive ? "+" : ""}
      {value.toFixed(1)}%
    </span>
  );
}

export default function SocialPage() {
  const [platform, setPlatform] = useState<Platform>("instagram");
  const [competitors, setCompetitors] = useState<CompetitorListItem[]>([]);
  const [igComparison, setIgComparison] = useState<any[]>([]);
  const [ttComparison, setTtComparison] = useState<any[]>([]);
  const [ytComparison, setYtComparison] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    async function loadAll() {
      try {
        const [comp, ig, tt, yt] = await Promise.allSettled([
          competitorsAPI.list(),
          instagramAPI.getComparison(),
          tiktokAPI.getComparison(),
          youtubeAPI.getComparison(),
        ]);
        if (comp.status === "fulfilled") setCompetitors(comp.value);
        if (ig.status === "fulfilled") setIgComparison(ig.value);
        if (tt.status === "fulfilled") setTtComparison(tt.value);
        if (yt.status === "fulfilled") setYtComparison(yt.value);
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
        if (platform === "instagram")
          return c.active_channels.includes("instagram");
        if (platform === "tiktok")
          return c.active_channels.includes("tiktok");
        if (platform === "youtube")
          return c.active_channels.includes("youtube");
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

  const currentData =
    platform === "instagram"
      ? igComparison
      : platform === "tiktok"
      ? ttComparison
      : ytComparison;

  const config = PLATFORM_CONFIG[platform];

  // Sort by primary metric (followers/subscribers)
  const sorted = [...currentData].sort((a, b) => {
    const aVal =
      platform === "youtube" ? a.subscribers || 0 : a.followers || 0;
    const bVal =
      platform === "youtube" ? b.subscribers || 0 : b.followers || 0;
    return bVal - aVal;
  });

  const leader = sorted[0];
  const challengers = sorted.slice(1);
  const maxFollowers = leader
    ? platform === "youtube"
      ? leader.subscribers || 1
      : leader.followers || 1
    : 1;

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
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
            <Activity className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">R&eacute;seaux sociaux</h1>
            <p className="text-[13px] text-muted-foreground">
              Comparaison multi-plateformes
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefreshAll}
          disabled={fetching}
          className="gap-2"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${fetching ? "animate-spin" : ""}`}
          />
          Rafra&icirc;chir
        </Button>
      </div>

      {/* Platform selector - gradient-accented pills */}
      <div className="flex items-center gap-1 p-1 rounded-full bg-card border border-border w-fit">
        {(["instagram", "tiktok", "youtube"] as Platform[]).map((p) => {
          const pConfig = PLATFORM_CONFIG[p];
          const pData =
            p === "instagram"
              ? igComparison
              : p === "tiktok"
              ? ttComparison
              : ytComparison;
          const isActive = platform === p;
          return (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              className={`relative px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
                isActive
                  ? "text-white shadow-lg"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {isActive && (
                <div
                  className={`absolute inset-0 rounded-full bg-gradient-to-r ${pConfig.gradient}`}
                />
              )}
              <span className="relative flex items-center gap-2">
                {pConfig.label}
                {pData.length > 0 && (
                  <span
                    className={`text-[10px] tabular-nums ${
                      isActive ? "text-white/70" : "text-muted-foreground"
                    }`}
                  >
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
          <h3 className="text-lg font-semibold text-foreground mb-1">
            Aucune donn&eacute;e {config.label}
          </h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Configurez des concurrents avec un compte {config.label}.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Leader spotlight */}
          {leader && (
            <div
              className={`relative rounded-2xl overflow-hidden bg-gradient-to-br ${config.darkBg} text-white p-8`}
            >
              <div className="absolute top-4 right-4 text-[11px] font-semibold uppercase tracking-widest text-white/40">
                #1 {config.label}
              </div>
              <div className="flex items-start justify-between">
                <div className="space-y-4">
                  <div>
                    <div className="text-[11px] uppercase tracking-widest text-white/50 mb-1">
                      Leader
                    </div>
                    <h3 className="text-2xl font-bold">
                      {platform === "youtube"
                        ? leader.channel_name || leader.competitor_name
                        : leader.competitor_name}
                    </h3>
                    {(leader.username || leader.channel_id) && (
                      <a
                        href={config.link(
                          leader.username || leader.channel_id
                        )}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-sm text-white/60 hover:text-white/80 mt-1 transition-colors"
                      >
                        {config.linkLabel(
                          leader.username || leader.channel_id
                        )}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  <div className="flex items-end gap-8">
                    <div>
                      <div className="text-4xl font-bold tabular-nums">
                        {formatNumber(
                          platform === "youtube"
                            ? leader.subscribers
                            : leader.followers
                        )}
                      </div>
                      <div className="text-xs text-white/50 mt-0.5">
                        {platform === "youtube"
                          ? "abonnes"
                          : "followers"}
                      </div>
                    </div>
                    {platform === "instagram" && (
                      <>
                        <div>
                          <div className="text-xl font-bold tabular-nums">
                            {leader.engagement_rate?.toFixed(2) || "0"}%
                          </div>
                          <div className="text-xs text-white/50 mt-0.5">
                            engagement
                          </div>
                        </div>
                        <div>
                          <div className="text-xl font-bold tabular-nums">
                            {formatNumber(leader.posts_count || 0)}
                          </div>
                          <div className="text-xs text-white/50 mt-0.5">
                            posts
                          </div>
                        </div>
                      </>
                    )}
                    {platform === "tiktok" && (
                      <>
                        <div>
                          <div className="text-xl font-bold tabular-nums">
                            {formatNumber(leader.likes || 0)}
                          </div>
                          <div className="text-xs text-white/50 mt-0.5">
                            likes
                          </div>
                        </div>
                        <div>
                          <div className="text-xl font-bold tabular-nums">
                            {formatNumber(leader.videos_count || 0)}
                          </div>
                          <div className="text-xs text-white/50 mt-0.5">
                            videos
                          </div>
                        </div>
                      </>
                    )}
                    {platform === "youtube" && (
                      <>
                        <div>
                          <div className="text-xl font-bold tabular-nums">
                            {formatNumber(leader.total_views || 0)}
                          </div>
                          <div className="text-xs text-white/50 mt-0.5">
                            vues totales
                          </div>
                        </div>
                        <div>
                          <div className="text-xl font-bold tabular-nums">
                            {formatNumber(leader.videos_count || 0)}
                          </div>
                          <div className="text-xs text-white/50 mt-0.5">
                            videos
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                  {leader.follower_growth_7d !== undefined && (
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-white/50">7 jours:</span>
                      <GrowthBadge value={leader.follower_growth_7d} />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Relative comparison bars */}
          <div className="space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
                <Users className="h-4 w-4 text-violet-600" />
              </div>
              <h3 className="text-[13px] font-semibold text-foreground">
                Audience compar&eacute;e
              </h3>
            </div>
            <div className="space-y-3">
              {sorted.map((c, i) => {
                const val =
                  platform === "youtube"
                    ? c.subscribers || 0
                    : c.followers || 0;
                const pct = (val / maxFollowers) * 100;
                return (
                  <div key={c.competitor_id} className="group">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span
                          className={`flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold ${
                            i === 0
                              ? `bg-gradient-to-r ${config.gradient} text-white`
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {i + 1}
                        </span>
                        <span className="text-sm font-medium">
                          {platform === "youtube"
                            ? c.channel_name || c.competitor_name
                            : c.competitor_name}
                        </span>
                        {(c.username || c.channel_id) && (
                          <a
                            href={config.link(c.username || c.channel_id)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`text-[11px] ${config.accent} hover:underline flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity`}
                          >
                            <ExternalLink className="h-2.5 w-2.5" />
                          </a>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        {(c.follower_growth_7d !== undefined ||
                          c.subscriber_growth_7d !== undefined) && (
                          <GrowthBadge
                            value={
                              c.follower_growth_7d ??
                              c.subscriber_growth_7d
                            }
                          />
                        )}
                        <span className="text-sm font-bold tabular-nums w-20 text-right">
                          {formatNumber(val)}
                        </span>
                      </div>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${
                          i === 0
                            ? `bg-gradient-to-r ${config.gradient}`
                            : "bg-slate-300 dark:bg-slate-600"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Detailed metrics table */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-5 py-3 border-b bg-muted/20 flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100">
                <BarChart3 className="h-3.5 w-3.5 text-slate-600" />
              </div>
              <span className="text-[12px] font-semibold text-foreground">
                D&eacute;tails par concurrent
              </span>
            </div>
            <table className="w-full">
              <thead>
                <tr className="bg-muted/30">
                  <th className="text-left text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                    Concurrent
                  </th>
                  <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                    {platform === "youtube" ? "Abonnes" : "Followers"}
                  </th>
                  {platform === "instagram" && (
                    <>
                      <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                        Engagement
                      </th>
                      <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                        Posts
                      </th>
                    </>
                  )}
                  {platform === "tiktok" && (
                    <>
                      <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                        Likes
                      </th>
                      <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                        Videos
                      </th>
                    </>
                  )}
                  {platform === "youtube" && (
                    <>
                      <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                        Vues totales
                      </th>
                      <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                        Videos
                      </th>
                    </>
                  )}
                  <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                    Croissance 7j
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((c, i) => {
                  const val =
                    platform === "youtube"
                      ? c.subscribers || 0
                      : c.followers || 0;
                  return (
                    <tr
                      key={c.competitor_id}
                      className={`border-t transition-colors hover:bg-muted/30 ${
                        i === 0 ? `${config.lightBg}` : ""
                      }`}
                    >
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <span
                            className={`flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-bold ${
                              i === 0
                                ? `bg-gradient-to-r ${config.gradient} text-white`
                                : "bg-muted text-muted-foreground"
                            }`}
                          >
                            {i + 1}
                          </span>
                          <div>
                            <span className="text-sm font-medium">
                              {platform === "youtube"
                                ? c.channel_name || c.competitor_name
                                : c.competitor_name}
                            </span>
                            {(c.username || c.channel_id) && (
                              <a
                                href={config.link(
                                  c.username || c.channel_id
                                )}
                                target="_blank"
                                rel="noopener noreferrer"
                                className={`block text-[11px] ${config.accent} hover:underline`}
                              >
                                {config.linkLabel(
                                  c.username || c.channel_id
                                )}
                              </a>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <span className="text-sm font-bold tabular-nums">
                          {formatNumber(val)}
                        </span>
                      </td>
                      {platform === "instagram" && (
                        <>
                          <td className="px-5 py-3.5 text-right">
                            <span className="text-sm tabular-nums">
                              {c.engagement_rate?.toFixed(2) || "0"}%
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <span className="text-sm tabular-nums">
                              {formatNumber(c.posts_count || 0)}
                            </span>
                          </td>
                        </>
                      )}
                      {platform === "tiktok" && (
                        <>
                          <td className="px-5 py-3.5 text-right">
                            <span className="text-sm tabular-nums">
                              {formatNumber(c.likes || 0)}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <span className="text-sm tabular-nums">
                              {formatNumber(c.videos_count || 0)}
                            </span>
                          </td>
                        </>
                      )}
                      {platform === "youtube" && (
                        <>
                          <td className="px-5 py-3.5 text-right">
                            <span className="text-sm tabular-nums">
                              {formatNumber(c.total_views || 0)}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-right">
                            <span className="text-sm tabular-nums">
                              {formatNumber(c.videos_count || 0)}
                            </span>
                          </td>
                        </>
                      )}
                      <td className="px-5 py-3.5 text-right">
                        <GrowthBadge
                          value={
                            c.follower_growth_7d ??
                            c.subscriber_growth_7d
                          }
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Platform-specific bonus insights */}
          {platform === "tiktok" && sorted.some((c) => c.likes > 0 && c.videos_count > 0) && (
            <div className="rounded-2xl border bg-card p-6 space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-100">
                  <Zap className="h-4 w-4 text-cyan-600" />
                </div>
                <h3 className="text-[13px] font-semibold text-foreground">
                  Performance par vid&eacute;o
                </h3>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {sorted
                  .filter((c) => c.likes > 0 && c.videos_count > 0)
                  .map((c) => (
                    <div
                      key={c.competitor_id}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/30"
                    >
                      <span className="text-sm">{c.competitor_name}</span>
                      <span className="text-sm font-bold tabular-nums">
                        {formatNumber(
                          Math.round(c.likes / c.videos_count)
                        )}{" "}
                        <span className="font-normal text-muted-foreground">
                          likes/vid
                        </span>
                      </span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {platform === "youtube" && sorted.some((c) => c.total_views > 0 && c.subscribers > 0) && (
            <div className="rounded-2xl border bg-card p-6 space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-100">
                  <BarChart3 className="h-4 w-4 text-red-600" />
                </div>
                <h3 className="text-[13px] font-semibold text-foreground">
                  Ratio vues / abonn&eacute;
                </h3>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {sorted
                  .filter((c) => c.total_views > 0 && c.subscribers > 0)
                  .map((c) => (
                    <div
                      key={c.competitor_id}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/30"
                    >
                      <span className="text-sm">
                        {c.channel_name || c.competitor_name}
                      </span>
                      <span className="text-sm font-bold tabular-nums">
                        {(c.total_views / c.subscribers).toFixed(0)}x
                      </span>
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
