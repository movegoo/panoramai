"use client";

import { useEffect, useState } from "react";
import {
  watchAPI,
  DashboardData,
  DashboardCompetitor,
  RankingCategory,
  AdIntelligence,
} from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Instagram,
  Youtube,
  Star,
  Crown,
  AlertTriangle,
  Heart,
  Music,
  Smartphone,
  ArrowUpRight,
  ArrowDownRight,
  Zap,
  MessageSquare,
  Download,
  Shield,
  Activity,
  Target,
  ChevronUp,
  ChevronDown,
  BarChart3,
  Trophy,
  Users,
  Lightbulb,
  Megaphone,
  Play,
  Image,
  Layers,
  Monitor,
} from "lucide-react";

/* ─────────────────────── Helpers ─────────────────────── */

function TrendBadge({ value }: { value?: number }) {
  const v = value ?? 0;
  if (v === 0)
    return (
      <span className="inline-flex items-center gap-0.5 text-[11px] text-gray-400 tabular-nums">
        <Minus className="h-3 w-3" /> 0%
      </span>
    );
  if (v > 0)
    return (
      <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-emerald-600 tabular-nums">
        <ArrowUpRight className="h-3 w-3" />+{v.toFixed(1)}%
      </span>
    );
  return (
    <span className="inline-flex items-center gap-0.5 text-[11px] font-semibold text-red-500 tabular-nums">
      <ArrowDownRight className="h-3 w-3" />{v.toFixed(1)}%
    </span>
  );
}

function Stars({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const half = rating - full >= 0.25;
  return (
    <span className="inline-flex items-center gap-px">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className={`h-3 w-3 ${
            i < full
              ? "fill-amber-400 text-amber-400"
              : i === full && half
              ? "fill-amber-400/50 text-amber-400"
              : "text-gray-200"
          }`}
        />
      ))}
    </span>
  );
}

function InsightIcon({ icon }: { icon: string }) {
  const c = "h-4 w-4";
  switch (icon) {
    case "crown": return <Crown className={c} />;
    case "trending-up": return <TrendingUp className={c} />;
    case "star": return <Star className={c} />;
    case "heart": return <Heart className={c} />;
    case "alert-triangle": return <AlertTriangle className={c} />;
    default: return <Zap className={c} />;
  }
}

function RankingIcon({ icon }: { icon: string }) {
  const c = "h-4 w-4";
  switch (icon) {
    case "trophy": return <Trophy className={c} />;
    case "instagram": return <Instagram className={c} />;
    case "music": return <Music className={c} />;
    case "youtube": return <Youtube className={c} />;
    case "star": return <Star className={c} />;
    case "heart": return <Heart className={c} />;
    case "users": return <Users className={c} />;
    default: return <BarChart3 className={c} />;
  }
}

function FormatIcon({ format }: { format: string }) {
  const c = "h-4 w-4";
  switch (format) {
    case "VIDEO": return <Play className={c} />;
    case "IMAGE": return <Image className={c} />;
    case "CAROUSEL": return <Layers className={c} />;
    case "DPA": return <Monitor className={c} />;
    case "DCO": return <Zap className={c} />;
    default: return <Megaphone className={c} />;
  }
}

function AppleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20.94c1.5 0 2.75 1.06 4 1.06 3 0 6-8 6-12.22A4.91 4.91 0 0 0 17 5c-2.22 0-4 1.44-5 2-1-.56-2.78-2-5-2a4.9 4.9 0 0 0-5 4.78C2 14 5 22 8 22c1.25 0 2.5-1.06 4-1.06Z" />
      <path d="M10 2c1 .5 2 2 2 5" />
    </svg>
  );
}

const RANK_COLORS = ["text-amber-500", "text-slate-400", "text-orange-400", "text-gray-400"];

const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-red-50 border-red-200 text-red-800",
  medium: "bg-amber-50 border-amber-200 text-amber-800",
  info: "bg-indigo-50 border-indigo-200 text-indigo-800",
};

/* ─────────────────────── Page ─────────────────────── */

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeRanking, setActiveRanking] = useState(0);

  useEffect(() => {
    watchAPI
      .getDashboard()
      .then(setData)
      .catch((e: Error) => setError(e.message || "Erreur"))
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement du dashboard...</span>
        </div>
      </div>
    );

  if (error || !data)
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center space-y-2">
          <AlertTriangle className="h-8 w-8 text-red-400 mx-auto" />
          <p className="text-red-500 font-medium">{error || "Erreur inconnue"}</p>
        </div>
      </div>
    );

  const { brand, competitors, insights, platform_leaders: pl, ad_intelligence: adI, rankings } = data;
  const allPlayersSorted = [...(brand ? [brand, ...competitors] : competitors)].sort((a, b) => b.score - a.score);

  return (
    <div className="space-y-8">
      {/* ── Hero header ────────────────────────────────── */}
      <div className="rounded-2xl bg-gradient-to-br from-indigo-950 via-[#1e1b4b] to-violet-950 p-5 sm:p-8 text-white relative overflow-hidden">
        <div className="absolute -top-20 -right-20 h-60 w-60 rounded-full bg-violet-400/[0.05]" />
        <div className="absolute -bottom-10 -left-10 h-40 w-40 rounded-full bg-indigo-400/[0.04]" />

        <div className="relative">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 mb-6">
            <div>
              <div className="flex items-center gap-3 mb-1">
                <Shield className="h-6 w-6 text-violet-400" />
                <h1 className="text-2xl font-bold tracking-tight">{data.brand_name}</h1>
                {brand && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                    brand.score >= 80 ? "bg-emerald-500/20 text-emerald-300" :
                    brand.score >= 50 ? "bg-amber-500/20 text-amber-300" :
                    "bg-red-500/20 text-red-300"
                  }`}>
                    Score {Math.round(brand.score)}/100
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-sm">
                Veille concurrentielle &mdash; {data.sector}
              </p>
            </div>
            <div className="text-right">
              <div className="text-[10px] text-slate-500 uppercase tracking-widest">Derniere maj</div>
              <div className="text-xs text-slate-400 mt-0.5 tabular-nums">
                {(() => { try { return new Date(data.last_updated).toLocaleString("fr-FR"); } catch { return data.last_updated; } })()}
              </div>
            </div>
          </div>

          {/* Platform leader cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {pl.instagram && (
              <div className="rounded-xl bg-white/[0.06] backdrop-blur-sm px-4 py-3 border border-white/[0.08]">
                <div className="flex items-center gap-2 mb-2">
                  <Instagram className="h-4 w-4 text-pink-400" />
                  <span className="text-[10px] text-pink-300 uppercase tracking-widest font-semibold">Instagram</span>
                </div>
                <div className="text-xl font-bold tabular-nums">{formatNumber(pl.instagram.value)}</div>
                <div className="text-[11px] text-slate-500 mt-0.5">{pl.instagram.leader}</div>
              </div>
            )}
            {pl.tiktok && (
              <div className="rounded-xl bg-white/[0.06] backdrop-blur-sm px-4 py-3 border border-white/[0.08]">
                <div className="flex items-center gap-2 mb-2">
                  <Music className="h-4 w-4 text-cyan-400" />
                  <span className="text-[10px] text-cyan-300 uppercase tracking-widest font-semibold">TikTok</span>
                </div>
                <div className="text-xl font-bold tabular-nums">{formatNumber(pl.tiktok.value)}</div>
                <div className="text-[11px] text-slate-500 mt-0.5">{pl.tiktok.leader}</div>
              </div>
            )}
            {pl.youtube && (
              <div className="rounded-xl bg-white/[0.06] backdrop-blur-sm px-4 py-3 border border-white/[0.08]">
                <div className="flex items-center gap-2 mb-2">
                  <Youtube className="h-4 w-4 text-red-400" />
                  <span className="text-[10px] text-red-300 uppercase tracking-widest font-semibold">YouTube</span>
                </div>
                <div className="text-xl font-bold tabular-nums">{formatNumber(pl.youtube.value)}</div>
                <div className="text-[11px] text-slate-500 mt-0.5">{pl.youtube.leader}</div>
              </div>
            )}
            {pl.playstore && (
              <div className="rounded-xl bg-white/[0.06] backdrop-blur-sm px-4 py-3 border border-white/[0.08]">
                <div className="flex items-center gap-2 mb-2">
                  <Smartphone className="h-4 w-4 text-emerald-400" />
                  <span className="text-[10px] text-emerald-300 uppercase tracking-widest font-semibold">Play Store</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-bold tabular-nums">{pl.playstore.value.toFixed(1)}</span>
                  <Stars rating={pl.playstore.value} />
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">{pl.playstore.leader}</div>
              </div>
            )}
            {pl.appstore && (
              <div className="rounded-xl bg-white/[0.06] backdrop-blur-sm px-4 py-3 border border-white/[0.08]">
                <div className="flex items-center gap-2 mb-2">
                  <AppleIcon className="h-4 w-4 text-blue-400" />
                  <span className="text-[10px] text-blue-300 uppercase tracking-widest font-semibold">App Store</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xl font-bold tabular-nums">{pl.appstore.value.toFixed(1)}</span>
                  <Stars rating={pl.appstore.value} />
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">{pl.appstore.leader}</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Two-column layout: Rankings + Ad Intelligence ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── CLASSEMENTS ────────────────────────────────── */}
        <div className="space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100">
              <Trophy className="h-4 w-4 text-amber-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Classements
            </h2>
          </div>

          {/* Ranking category tabs */}
          <div className="flex flex-wrap gap-1.5">
            {rankings.map((rk, idx) => (
              <button
                key={rk.id}
                onClick={() => setActiveRanking(idx)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeRanking === idx
                    ? "bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-sm"
                    : "bg-card text-muted-foreground hover:bg-muted border border-border"
                }`}
              >
                <RankingIcon icon={rk.icon} />
                {rk.label}
              </button>
            ))}
          </div>

          {/* Active ranking leaderboard */}
          {rankings[activeRanking] && (
            <div className="rounded-2xl border bg-card overflow-hidden">
              <div className="divide-y">
                {rankings[activeRanking].entries.map((entry) => {
                  const isBrand = entry.is_brand;
                  return (
                    <div
                      key={entry.name}
                      className={`flex items-center gap-3 px-4 py-3 transition-colors ${
                        isBrand ? "bg-violet-50/60" : "hover:bg-muted/20"
                      }`}
                    >
                      <div className={`flex items-center justify-center h-7 w-7 rounded-lg text-xs font-bold ${
                        entry.rank === 1 ? "bg-amber-100 text-amber-700" :
                        entry.rank === 2 ? "bg-slate-100 text-slate-600" :
                        entry.rank === 3 ? "bg-orange-100 text-orange-600" :
                        "bg-gray-50 text-gray-500"
                      }`}>
                        {entry.rank === 1 ? <Crown className="h-3.5 w-3.5" /> : entry.rank}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className={`text-sm font-medium ${isBrand ? "text-violet-700" : ""}`}>
                          {entry.name}
                          {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                        </span>
                        {entry.extra && (
                          <span className="ml-2 text-[10px] text-muted-foreground">{entry.extra}</span>
                        )}
                      </div>
                      <div className="text-right">
                        <span className={`text-sm font-bold tabular-nums ${isBrand ? "text-violet-700" : ""}`}>
                          {entry.formatted}
                        </span>
                      </div>
                      {/* Visual bar */}
                      <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full ${isBrand ? "bg-violet-500" : "bg-foreground/20"}`}
                          style={{
                            width: `${rankings[activeRanking].entries.length > 0
                              ? (entry.value / rankings[activeRanking].entries[0].value) * 100
                              : 0}%`
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* ── INTELLIGENCE PUBLICITAIRE ───────────────────── */}
        <div className="space-y-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
              <Megaphone className="h-4 w-4 text-violet-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Intelligence publicitaire
            </h2>
            <span className="ml-auto text-[11px] text-muted-foreground tabular-nums bg-muted px-2 py-0.5 rounded-full">{adI.total_ads} pubs</span>
          </div>

          {/* Ad volume comparison */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/20">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Volume par annonceur / payeur
              </span>
            </div>
            <div className="divide-y">
              {adI.competitor_summary.map((cs) => {
                const maxAds = Math.max(...adI.competitor_summary.map(c => c.total_ads), 1);
                const pct = (cs.total_ads / maxAds) * 100;
                return (
                  <div key={cs.id} className={`px-4 py-3 ${cs.is_brand ? "bg-violet-50/60" : ""}`}>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className={`text-sm font-medium ${cs.is_brand ? "text-violet-700" : ""}`}>
                        {cs.name}
                        {cs.is_brand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                      </span>
                      <span className="text-sm font-bold tabular-nums">{cs.total_ads} pubs</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${cs.is_brand ? "bg-violet-500" : "bg-violet-400"}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <div className="flex gap-1">
                        {Object.entries(cs.formats).slice(0, 3).map(([fmt, count]) => (
                          <span key={fmt} className="text-[9px] bg-muted px-1.5 py-0.5 rounded-md text-muted-foreground">
                            {fmt} ({count})
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-1 mt-1.5">
                      {cs.platforms.map((p) => (
                        <span key={p} className="text-[9px] text-muted-foreground/60">{p}</span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Format breakdown */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/20">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Formats publicitaires du marche
              </span>
            </div>
            <div className="p-4 grid grid-cols-2 sm:grid-cols-3 gap-3">
              {adI.format_breakdown.map((fb) => (
                <div key={fb.format} className="text-center rounded-xl bg-muted/30 p-3">
                  <FormatIcon format={fb.format} />
                  <div className="text-lg font-bold tabular-nums mt-1">{fb.pct}%</div>
                  <div className="text-[10px] text-muted-foreground">{fb.label}</div>
                  <div className="text-[10px] text-muted-foreground/60">{fb.count} pubs</div>
                </div>
              ))}
            </div>
          </div>

          {/* Platform diffusion breakdown */}
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b bg-muted/20">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Plateformes de diffusion
              </span>
            </div>
            <div className="p-4 space-y-2.5">
              {adI.platform_breakdown.map((pb) => {
                const maxCount = Math.max(...adI.platform_breakdown.map(p => p.count), 1);
                const barPct = (pb.count / maxCount) * 100;
                return (
                  <div key={pb.platform} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium capitalize">{pb.platform.toLowerCase().replace("_", " ")}</span>
                      <span className="text-xs tabular-nums text-muted-foreground">{pb.count} pubs ({pb.pct}%)</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-violet-400 to-indigo-600 transition-all duration-700" style={{ width: `${barPct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
            {/* Per-competitor platform usage */}
            <div className="px-4 pb-4 pt-2 border-t">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-2">Par concurrent</div>
              <div className="space-y-2">
                {adI.competitor_summary.map((cs) => (
                  <div key={cs.id} className="flex items-center gap-2 flex-wrap">
                    <span className={`text-[11px] font-semibold min-w-[80px] ${cs.is_brand ? "text-violet-700" : ""}`}>
                      {cs.name}
                    </span>
                    {cs.platforms.sort().map((p) => (
                      <span key={p} className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-100">
                        {p.toLowerCase().replace("_", " ")}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── RECOMMANDATIONS ─────────────────────────────── */}
      {adI.recommendations.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100">
              <Lightbulb className="h-4 w-4 text-amber-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Recommandations stratégiques
            </h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {adI.recommendations.map((rec, i) => (
              <div
                key={i}
                className={`flex items-start gap-3 p-4 rounded-xl border text-[13px] leading-relaxed ${PRIORITY_STYLE[rec.priority] || "bg-muted/30 border-border"}`}
              >
                <div className="mt-0.5 shrink-0">
                  {rec.priority === "high" ? <AlertTriangle className="h-4 w-4" /> :
                   rec.priority === "medium" ? <Lightbulb className="h-4 w-4" /> :
                   <Zap className="h-4 w-4" />}
                </div>
                <div>
                  <div className="font-medium mb-0.5">{rec.text}</div>
                  {rec.market_share_pct > 0 && (
                    <div className="flex items-center gap-2 mt-1.5">
                      <div className="h-1.5 w-20 rounded-full bg-black/10 overflow-hidden">
                        <div className="h-full rounded-full bg-current" style={{ width: `${Math.min(rec.market_share_pct, 100)}%` }} />
                      </div>
                      <span className="text-[10px] tabular-nums">{rec.market_share_pct}% du marche</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Insights strip ─────────────────────────────── */}
      {insights.length > 0 && (
        <div className="rounded-2xl border bg-card overflow-hidden">
          <div className="px-4 py-2.5 border-b bg-muted/20 flex items-center gap-2">
            <Activity className="h-3.5 w-3.5 text-indigo-500" />
            <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Insights
            </span>
            <span className="text-[10px] text-muted-foreground/60 ml-auto">{insights.length} signaux</span>
          </div>
          <div className="divide-y">
            {insights.map((ins, i) => {
              const sev = ins.severity;
              const dotColor =
                sev === "success" ? "bg-emerald-500" :
                sev === "warning" ? "bg-amber-500" :
                sev === "danger" ? "bg-red-500" :
                "bg-indigo-500";
              const iconColor =
                sev === "success" ? "text-emerald-500" :
                sev === "warning" ? "text-amber-500" :
                sev === "danger" ? "text-red-500" :
                "text-indigo-500";
              return (
                <div key={i} className="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/20 transition-colors">
                  <div className={`shrink-0 ${iconColor}`}>
                    <InsightIcon icon={ins.icon} />
                  </div>
                  <span className="text-[13px] text-foreground/90">{ins.text}</span>
                  <div className={`ml-auto shrink-0 h-2 w-2 rounded-full ${dotColor}`} />
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Competitor cards ───────────────────────────── */}
      <div className="space-y-5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
            <Users className="h-4 w-4 text-blue-600" />
          </div>
          <h2 className="text-[13px] font-semibold text-foreground">
            Concurrents
          </h2>
        </div>
        <div className="space-y-4">
          {[...competitors].sort((a, b) => b.score - a.score).map((comp) => {
            const maxSocial = Math.max(...competitors.map((c) => c.total_social), 1);
            const socialPct = (comp.total_social / maxSocial) * 100;
            const { instagram: ig, tiktok: tt, youtube: yt, playstore: ps, appstore: as_ } = comp;

            // Find ad data for this competitor
            const compAds = adI.competitor_summary.find(c => c.id === comp.id);

            return (
              <div
                key={comp.id}
                className="rounded-2xl border bg-card overflow-hidden transition-shadow hover:shadow-lg"
              >
                <div className="flex items-center gap-4 px-5 py-4">
                  <div className={`flex items-center justify-center h-9 w-9 rounded-xl text-sm font-bold ${
                    comp.rank === 1 ? "bg-gradient-to-br from-amber-400 to-yellow-500 text-white shadow-lg shadow-amber-200/40" :
                    comp.rank === 2 ? "bg-gradient-to-br from-slate-300 to-slate-400 text-white shadow-lg shadow-slate-200/40" :
                    comp.rank === 3 ? "bg-gradient-to-br from-orange-300 to-orange-400 text-white shadow-lg shadow-orange-200/40" :
                    "bg-gray-100 text-gray-500"
                  }`}>
                    {comp.rank === 1 ? <Crown className="h-4 w-4" /> : comp.rank}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-lg truncate">{comp.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatNumber(comp.total_social)} reach social
                      {compAds && compAds.total_ads > 0 && (
                        <span className="ml-2">&middot; {compAds.total_ads} pubs actives</span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`inline-flex items-center justify-center h-10 w-10 rounded-xl text-sm font-bold ${
                      comp.score >= 80 ? "bg-emerald-100 text-emerald-700" :
                      comp.score >= 50 ? "bg-amber-100 text-amber-700" :
                      "bg-red-100 text-red-700"
                    }`}>
                      {Math.round(comp.score)}
                    </div>
                  </div>
                </div>

                {/* Social reach bar */}
                <div className="px-5 pb-1">
                  <div className="h-1 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-blue-500 via-violet-500 to-pink-500 transition-all duration-1000"
                      style={{ width: `${socialPct}%` }}
                    />
                  </div>
                </div>

                {/* Metrics grid */}
                <div className="px-5 py-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                  <div className={`rounded-xl px-3 py-2.5 ${ig ? "bg-pink-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Instagram className="h-3.5 w-3.5 text-pink-500" />
                      <span className="text-[10px] text-pink-600 font-semibold uppercase">IG</span>
                    </div>
                    {ig ? (
                      <div className="text-sm font-bold tabular-nums">{formatNumber(ig.followers)}</div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${tt && tt.followers > 0 ? "bg-cyan-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Music className="h-3.5 w-3.5 text-cyan-600" />
                      <span className="text-[10px] text-cyan-600 font-semibold uppercase">TT</span>
                    </div>
                    {tt && tt.followers > 0 ? (
                      <div className="text-sm font-bold tabular-nums">{formatNumber(tt.followers)}</div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${yt ? "bg-red-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Youtube className="h-3.5 w-3.5 text-red-500" />
                      <span className="text-[10px] text-red-600 font-semibold uppercase">YT</span>
                    </div>
                    {yt ? (
                      <div className="text-sm font-bold tabular-nums">{formatNumber(yt.subscribers)}</div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${ps?.rating ? "bg-emerald-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <Smartphone className="h-3.5 w-3.5 text-emerald-600" />
                      <span className="text-[10px] text-emerald-700 font-semibold uppercase">Play</span>
                    </div>
                    {ps?.rating ? (
                      <div className="flex items-center gap-1">
                        <span className="text-sm font-bold tabular-nums">{ps.rating.toFixed(1)}</span>
                        <Stars rating={ps.rating} />
                      </div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  <div className={`rounded-xl px-3 py-2.5 ${as_?.rating ? "bg-blue-50/70" : "bg-muted/30"}`}>
                    <div className="flex items-center gap-1.5 mb-1">
                      <AppleIcon className="h-3.5 w-3.5 text-blue-600" />
                      <span className="text-[10px] text-blue-700 font-semibold uppercase">Apple</span>
                    </div>
                    {as_?.rating ? (
                      <div className="flex items-center gap-1">
                        <span className="text-sm font-bold tabular-nums">{as_.rating.toFixed(1)}</span>
                        <Stars rating={as_.rating} />
                      </div>
                    ) : <div className="text-xs text-muted-foreground">&mdash;</div>}
                  </div>

                  {/* Ad formats used */}
                  <div className="rounded-xl px-3 py-2.5 bg-violet-50/70">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Megaphone className="h-3.5 w-3.5 text-violet-600" />
                      <span className="text-[10px] text-violet-700 font-semibold uppercase">Pubs</span>
                    </div>
                    {compAds && compAds.total_ads > 0 ? (
                      <>
                        <div className="text-sm font-bold tabular-nums">{compAds.total_ads}</div>
                        <div className="flex flex-wrap gap-0.5 mt-0.5">
                          {Object.keys(compAds.formats).slice(0, 3).map(f => (
                            <span key={f} className="text-[8px] bg-violet-100 text-violet-600 px-1 py-px rounded">{f}</span>
                          ))}
                        </div>
                      </>
                    ) : <div className="text-xs text-muted-foreground">Aucune</div>}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Vue comparative ───────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100">
            <BarChart3 className="h-4 w-4 text-slate-600" />
          </div>
          <h2 className="text-[13px] font-semibold text-foreground">
            Vue comparative
          </h2>
        </div>
        <div className="rounded-2xl border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/30">
                  <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground w-8">#</th>
                  <th className="text-left px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Acteur</th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Instagram className="h-3 w-3 text-pink-500" />IG</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Music className="h-3 w-3 text-cyan-500" />TT</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Youtube className="h-3 w-3 text-red-500" />YT</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Star className="h-3 w-3 text-amber-500" />Apps</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    <span className="inline-flex items-center gap-1"><Megaphone className="h-3 w-3 text-violet-500" />Pubs</span>
                  </th>
                  <th className="text-right px-4 py-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Score</th>
                </tr>
              </thead>
              <tbody>
                {allPlayersSorted.map((comp, idx) => {
                  const isBrand = comp.name.toLowerCase() === data.brand_name.toLowerCase();
                  const compAds = adI.competitor_summary.find(c => c.id === comp.id);
                  return (
                    <tr
                      key={comp.id}
                      className={`border-b last:border-0 transition-colors ${
                        isBrand ? "bg-violet-50/60 hover:bg-violet-50" : "hover:bg-muted/20"
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className={`flex items-center justify-center h-6 w-6 rounded-md text-[11px] font-bold ${
                          idx === 0 ? "bg-amber-100 text-amber-700" :
                          idx === 1 ? "bg-slate-100 text-slate-600" :
                          idx === 2 ? "bg-orange-100 text-orange-600" :
                          "bg-gray-50 text-gray-500"
                        }`}>
                          {idx + 1}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`font-medium ${isBrand ? "text-violet-700" : ""}`}>
                          {comp.name}
                          {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.instagram ? formatNumber(comp.instagram.followers) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.tiktok && comp.tiktok.followers > 0 ? formatNumber(comp.tiktok.followers) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.youtube ? formatNumber(comp.youtube.subscribers) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {comp.avg_app_rating ? comp.avg_app_rating.toFixed(1) : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {compAds && compAds.total_ads > 0 ? compAds.total_ads : <span className="text-muted-foreground">&mdash;</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className={`inline-flex items-center justify-center px-2.5 py-1 rounded-lg text-xs font-bold ${
                          comp.score >= 80 ? "bg-emerald-100 text-emerald-700" :
                          comp.score >= 50 ? "bg-amber-100 text-amber-700" :
                          "bg-red-100 text-red-700"
                        }`}>
                          {Math.round(comp.score)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Payeurs & Annonceurs detail ────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Payeurs (qui paye les pubs) */}
        <div className="space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100">
              <Shield className="h-4 w-4 text-emerald-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Payeurs
            </h2>
            <span className="ml-auto text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">{adI.payers.length} entités</span>
          </div>
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="divide-y">
              {adI.payers.map((payer) => {
                const maxTotal = Math.max(...adI.payers.map(p => p.total), 1);
                const pct = (payer.total / maxTotal) * 100;
                return (
                  <div key={payer.name} className="px-4 py-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-medium text-sm truncate">{payer.name}</span>
                        {payer.is_explicit && (
                          <span className="shrink-0 text-[8px] bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">
                            Verifie
                          </span>
                        )}
                      </div>
                      <span className="text-sm font-bold tabular-nums shrink-0 ml-2">{payer.total}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden mb-1.5">
                      <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                      <span className="text-emerald-600 font-medium">{payer.active} actives</span>
                      {payer.pages.length > 1 && (
                        <span>{payer.pages.length} pages</span>
                      )}
                      {payer.pages.length === 1 && payer.pages[0] !== payer.name && (
                        <span>via {payer.pages[0]}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Annonceurs (pages qui diffusent) */}
        <div className="space-y-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
              <Users className="h-4 w-4 text-violet-600" />
            </div>
            <h2 className="text-[13px] font-semibold text-foreground">
              Annonceurs (pages)
            </h2>
            <span className="ml-auto text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">{adI.advertisers.length} pages</span>
          </div>
          <div className="rounded-2xl border bg-card overflow-hidden">
            <div className="divide-y">
              {adI.advertisers.map((adv) => {
                const maxTotal = Math.max(...adI.advertisers.map(a => a.total), 1);
                const pct = (adv.total / maxTotal) * 100;
                return (
                  <div key={adv.name} className="px-4 py-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-medium text-sm truncate">{adv.name}</span>
                      <span className="text-sm font-bold tabular-nums shrink-0 ml-2">{adv.total}</span>
                    </div>
                    <div className="h-1.5 rounded-full bg-muted overflow-hidden mb-1.5">
                      <div className="h-full rounded-full bg-gradient-to-r from-violet-400 to-purple-500" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
                      <span className="text-violet-600 font-medium">{adv.active} actives</span>
                      {adv.top_format && (
                        <span className="bg-muted px-1.5 py-0.5 rounded">Top: {adv.top_format}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
