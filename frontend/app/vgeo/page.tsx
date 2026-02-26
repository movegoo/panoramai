"use client";

import React, { useState, useMemo } from "react";
import {
  Eye, RefreshCw, BarChart3, TrendingUp, Youtube, Video,
  Sparkles, Zap, Bot, Star, Search, ArrowRight, Target,
  Clock, Trophy, AlertTriangle, CheckCircle2, XCircle,
  Minus, Play, ThumbsUp,
} from "lucide-react";
import { vgeoAPI } from "@/lib/api";
import { useAPI } from "@/lib/use-api";
import { SmartFilter } from "@/components/smart-filter";

// ---------------------------------------------------------------------------
// Platform config
// ---------------------------------------------------------------------------
const LLM_CONFIG: Record<string, { label: string; color: string; bg: string; icon: string }> = {
  mistral: { label: "Mistral", color: "text-orange-600", bg: "bg-orange-100", icon: "https://mistral.ai/favicon.ico" },
  claude: { label: "Claude", color: "text-amber-700", bg: "bg-amber-100", icon: "https://claude.ai/favicon.ico" },
  gemini: { label: "Gemini", color: "text-blue-600", bg: "bg-blue-100", icon: "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Google-gemini-icon.svg/3840px-Google-gemini-icon.svg.png" },
  chatgpt: { label: "ChatGPT", color: "text-emerald-600", bg: "bg-emerald-100", icon: "https://chatgpt.com/favicon.ico" },
};

const CLASSIFICATION_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  HELP: { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-200", label: "HELP" },
  HUB: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-200", label: "HUB" },
  HERO: { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-200", label: "HERO" },
  UNKNOWN: { bg: "bg-gray-100", text: "text-gray-500", border: "border-gray-200", label: "?" },
};

// ---------------------------------------------------------------------------
// Score gauge component
// ---------------------------------------------------------------------------
function ScoreGauge({ score, size = 120 }: { score: number; size?: number }) {
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color = score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" className="text-gray-200" strokeWidth={8} />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth={8}
          strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={circumference - progress}
          className="transition-all duration-1000" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold" style={{ color }}>{score}</span>
        <span className="text-[10px] text-muted-foreground font-medium">/100</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-score bar
// ---------------------------------------------------------------------------
function SubScoreBar({ label, score, weight, icon: Icon }: { label: string; score: number; weight: string; icon: any }) {
  const color = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-3">
      <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-foreground">{label}</span>
          <span className="text-xs text-muted-foreground">{weight}</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${score}%` }} />
        </div>
      </div>
      <span className="text-sm font-bold text-foreground w-10 text-right">{score}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function VGeoPage() {
  const [aiFilters, setAiFilters] = useState<Record<string, any> | null>(null);
  const [aiInterpretation, setAiInterpretation] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<string | null>(null);

  // Fetch latest report
  const { data: report, isLoading, mutate: refreshReport } = useAPI<any>("/vgeo/report");

  const hasReport = report?.has_report;

  async function handleAnalyze() {
    setAnalyzing(true);
    setAnalyzeResult(null);
    try {
      const res = await vgeoAPI.analyze();
      setAnalyzeResult(`Analyse terminee ! Score VGEO : ${res.score?.total}/100`);
      refreshReport();
    } catch (e: any) {
      setAnalyzeResult(`Erreur: ${e.message}`);
    } finally {
      setAnalyzing(false);
    }
  }

  // Extract data from report
  const score = report?.score;
  const brandChannel = report?.brand_channel;
  const competitors = report?.competitors || [];
  const videos = report?.videos || [];
  const citations = report?.citations || {};
  const diagnostic = report?.diagnostic || "";
  const forces = report?.forces || [];
  const faiblesses = report?.faiblesses || [];
  const strategy = report?.strategy || [];
  const actions = report?.actions || [];

  // Classification counts for brand
  const brandVideos = useMemo(() => videos.filter((v: any) => v.is_brand), [videos]);
  const helpCount = useMemo(() => brandVideos.filter((v: any) => v.classification === "HELP").length, [brandVideos]);
  const hubCount = useMemo(() => brandVideos.filter((v: any) => v.classification === "HUB").length, [brandVideos]);
  const heroCount = useMemo(() => brandVideos.filter((v: any) => v.classification === "HERO").length, [brandVideos]);
  const totalBrandVideos = brandVideos.length || 1;

  // Filter videos based on AI filters
  const filteredVideos = useMemo(() => {
    if (!videos.length) return videos;
    if (!aiFilters) return videos;
    let filtered = [...videos];
    if (aiFilters.competitor_name?.length) {
      const names = aiFilters.competitor_name.map((n: string) => n.toLowerCase());
      filtered = filtered.filter((v: any) => names.some((n: string) => v.channel_name.toLowerCase().includes(n)));
    }
    if (aiFilters.classification?.length) {
      filtered = filtered.filter((v: any) => aiFilters.classification.includes(v.classification));
    }
    if (aiFilters.text_search) {
      const q = aiFilters.text_search.toLowerCase();
      filtered = filtered.filter((v: any) => v.title.toLowerCase().includes(q) || v.channel_name.toLowerCase().includes(q));
    }
    return filtered;
  }, [videos, aiFilters]);

  // Build citation matrix: query -> platform -> brands mentioned
  const citationMatrix = useMemo(() => {
    const matrix: Record<string, Record<string, string[]>> = {};
    for (const [platform, mentions] of Object.entries(citations)) {
      if (!Array.isArray(mentions)) continue;
      for (const m of mentions as any[]) {
        const query = m.query || "";
        if (!matrix[query]) matrix[query] = {};
        if (!matrix[query][platform]) matrix[query][platform] = [];
        if (m.brand && !matrix[query][platform].includes(m.brand)) {
          matrix[query][platform].push(m.brand);
        }
      }
    }
    return matrix;
  }, [citations]);

  // Empty state
  if (!isLoading && !hasReport) {
    return (
      <div className="space-y-6">
        <VGeoHeader handleAnalyze={handleAnalyze} analyzing={analyzing} />
        {analyzeResult && (
          <div className="rounded-xl bg-violet-50 border border-violet-200 px-4 py-3 text-sm text-violet-700">
            {analyzeResult}
          </div>
        )}
        <div className="rounded-2xl border bg-card p-8 text-center space-y-4">
          <div className="flex justify-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-200/50">
              <Youtube className="h-7 w-7 text-white" />
            </div>
          </div>
          <h3 className="text-base font-semibold">VGEO — Video Generative Engine Optimization</h3>
          <p className="text-sm text-muted-foreground max-w-lg mx-auto">
            Analysez votre strategie YouTube pour maximiser votre visibilite dans les moteurs IA (ChatGPT, Claude, Gemini, Mistral).
            Le framework HELP/HUB/HERO identifie les contenus que les LLM citent le plus.
          </p>
          <button onClick={handleAnalyze} disabled={analyzing}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold hover:shadow-lg hover:shadow-violet-200/50 disabled:opacity-50 transition-all">
            {analyzing ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            {analyzing ? "Analyse en cours..." : "Lancer l'analyse VGEO"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <VGeoHeader handleAnalyze={handleAnalyze} analyzing={analyzing} />

      {analyzeResult && (
        <div className="rounded-xl bg-violet-50 border border-violet-200 px-4 py-3 text-sm text-violet-700">
          {analyzeResult}
        </div>
      )}

      {/* Smart Filter */}
      <SmartFilter
        page="vgeo"
        placeholder="Filtrer... (ex: videos HELP, concurrent Leclerc, mot-cle tutoriel)"
        onFilter={(filters, interp) => { setAiFilters(filters); setAiInterpretation(interp); }}
        onClear={() => { setAiFilters(null); setAiInterpretation(""); }}
      />

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-6 w-6 animate-spin text-violet-500" />
          <span className="ml-3 text-muted-foreground">Chargement du rapport VGEO...</span>
        </div>
      ) : score ? (
        <>
          {/* ── Section 1: Score VGEO global ── */}
          <div className="rounded-2xl border border-border bg-card p-6">
            <div className="flex flex-col lg:flex-row items-center gap-8">
              {/* Gauge */}
              <div className="flex flex-col items-center gap-2">
                <ScoreGauge score={score.total} size={140} />
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Score VGEO</span>
                {brandChannel && (
                  <div className="flex items-center gap-1.5 mt-1">
                    <Youtube className="h-4 w-4 text-red-500" />
                    <span className="text-xs text-muted-foreground">{brandChannel.video_count} videos</span>
                  </div>
                )}
              </div>

              {/* Sub-scores */}
              <div className="flex-1 w-full space-y-4">
                <SubScoreBar label="Alignement" score={score.alignment} weight="35%" icon={Target} />
                <SubScoreBar label="Fraicheur" score={score.freshness} weight="30%" icon={Clock} />
                <SubScoreBar label="Presence IA" score={score.presence} weight="20%" icon={Eye} />
                <SubScoreBar label="Competitivite" score={score.competitivity} weight="15%" icon={Trophy} />
              </div>
            </div>

            {/* Explanation */}
            <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="rounded-lg bg-violet-50 border border-violet-100 p-3 text-center">
                <p className="text-xs text-muted-foreground">Alignement</p>
                <p className="text-[10px] text-violet-600 mt-0.5">Videos vs requetes LLM</p>
              </div>
              <div className="rounded-lg bg-violet-50 border border-violet-100 p-3 text-center">
                <p className="text-xs text-muted-foreground">Fraicheur</p>
                <p className="text-[10px] text-violet-600 mt-0.5">Contenu recent {"<"} 3 mois</p>
              </div>
              <div className="rounded-lg bg-violet-50 border border-violet-100 p-3 text-center">
                <p className="text-xs text-muted-foreground">Presence</p>
                <p className="text-[10px] text-violet-600 mt-0.5">Cite par les moteurs IA</p>
              </div>
              <div className="rounded-lg bg-violet-50 border border-violet-100 p-3 text-center">
                <p className="text-xs text-muted-foreground">Competitivite</p>
                <p className="text-[10px] text-violet-600 mt-0.5">Position vs concurrents</p>
              </div>
            </div>
          </div>

          {/* ── Section 2: Classification HELP/HUB/HERO ── */}
          {brandVideos.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <Video className="h-4 w-4 text-violet-500" />
                Classification HELP / HUB / HERO
              </h2>

              {/* Distribution bars */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                {[
                  { key: "HELP", count: helpCount, desc: "Tutoriels, FAQ, guides", icon: Search },
                  { key: "HUB", count: hubCount, desc: "Series, contenu recurrent", icon: Play },
                  { key: "HERO", count: heroCount, desc: "Evenements, campagnes", icon: Star },
                ].map(item => {
                  const pct = Math.round((item.count / totalBrandVideos) * 100);
                  const cfg = CLASSIFICATION_COLORS[item.key];
                  return (
                    <div key={item.key} className={`rounded-xl border ${cfg.border} ${cfg.bg} p-4`}>
                      <div className="flex items-center gap-2 mb-2">
                        <item.icon className={`h-4 w-4 ${cfg.text}`} />
                        <span className={`text-sm font-bold ${cfg.text}`}>{item.key}</span>
                      </div>
                      <p className="text-2xl font-bold text-foreground">{item.count}</p>
                      <p className="text-[10px] text-muted-foreground">{pct}% — {item.desc}</p>
                    </div>
                  );
                })}
              </div>

              {/* Stacked bar */}
              <div className="h-4 rounded-full overflow-hidden flex mb-4">
                {helpCount > 0 && <div className="bg-emerald-500 transition-all" style={{ width: `${(helpCount / totalBrandVideos) * 100}%` }} />}
                {hubCount > 0 && <div className="bg-blue-500 transition-all" style={{ width: `${(hubCount / totalBrandVideos) * 100}%` }} />}
                {heroCount > 0 && <div className="bg-amber-500 transition-all" style={{ width: `${(heroCount / totalBrandVideos) * 100}%` }} />}
              </div>

              {/* Video list */}
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {filteredVideos.slice(0, 30).map((v: any, i: number) => {
                  const cfg = CLASSIFICATION_COLORS[v.classification] || CLASSIFICATION_COLORS.UNKNOWN;
                  return (
                    <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-muted/40 transition-colors">
                      <span className={`shrink-0 inline-flex items-center justify-center w-14 h-6 rounded text-[10px] font-bold ${cfg.bg} ${cfg.text} border ${cfg.border}`}>
                        {cfg.label}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">{v.title}</p>
                        <p className="text-[10px] text-muted-foreground">
                          {v.channel_name}
                          {v.is_brand && <span className="ml-1 text-violet-600 font-bold">(vous)</span>}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                        {v.views > 0 && (
                          <span className="flex items-center gap-1">
                            <Eye className="h-3 w-3" />
                            {v.views >= 1000 ? `${(v.views / 1000).toFixed(0)}K` : v.views}
                          </span>
                        )}
                        {v.likes > 0 && (
                          <span className="flex items-center gap-1">
                            <ThumbsUp className="h-3 w-3" />
                            {v.likes >= 1000 ? `${(v.likes / 1000).toFixed(0)}K` : v.likes}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Section 3: Citations LLM ── */}
          {Object.keys(citationMatrix).length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <Bot className="h-4 w-4 text-indigo-500" />
                Citations dans les moteurs IA
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">Requete</th>
                      {["claude", "gemini", "chatgpt", "mistral"].map(p => (
                        <th key={p} className="text-center py-2 px-3">
                          <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${LLM_CONFIG[p]?.color || ""}`}>
                            {LLM_CONFIG[p] && <img src={LLM_CONFIG[p].icon} alt={LLM_CONFIG[p].label} className="h-4 w-4 rounded-sm object-contain" />}
                            {LLM_CONFIG[p]?.label || p}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(citationMatrix).slice(0, 20).map(([query, platforms]) => (
                      <tr key={query} className="border-b border-border/50 hover:bg-muted/30">
                        <td className="py-2.5 pr-4 text-xs font-medium text-foreground max-w-[300px] truncate">{query}</td>
                        {["claude", "gemini", "chatgpt", "mistral"].map(p => {
                          const brands = platforms[p] || [];
                          const hasBrand = brands.length > 0;
                          return (
                            <td key={p} className="text-center py-2.5 px-3">
                              {hasBrand ? (
                                <span className="inline-flex items-center gap-1 text-xs">
                                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                                  <span className="text-emerald-700 font-medium">{brands.length}</span>
                                </span>
                              ) : (
                                <Minus className="h-3.5 w-3.5 text-gray-300 mx-auto" />
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Section 4: Comparaison concurrents ── */}
          {competitors.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-violet-500" />
                Comparaison concurrents
              </h2>
              <div className="space-y-3">
                {/* Brand first */}
                {score && (
                  <div className="flex items-center gap-3">
                    <span className="w-32 text-sm font-bold text-violet-700 truncate flex items-center gap-1">
                      Votre marque
                      <span className="text-[9px] font-bold text-violet-600 bg-violet-100 rounded px-1 py-0.5">vous</span>
                    </span>
                    <div className="flex-1 h-7 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all"
                        style={{ width: `${score.total}%` }} />
                    </div>
                    <span className="text-sm font-bold text-violet-700 w-12 text-right">{score.total}</span>
                  </div>
                )}
                {competitors
                  .sort((a: any, b: any) => (b.score?.total || 0) - (a.score?.total || 0))
                  .map((c: any, i: number) => {
                    const cScore = c.score?.total || 0;
                    const barColor = cScore >= 70 ? "bg-emerald-500" : cScore >= 40 ? "bg-amber-500" : "bg-red-400";
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <span className="w-32 text-sm font-medium text-foreground truncate">{c.name}</span>
                        <div className="flex-1 h-7 bg-gray-100 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full transition-all ${barColor}`}
                            style={{ width: `${cScore}%` }} />
                        </div>
                        <span className="text-sm font-semibold text-foreground w-12 text-right">{cScore}</span>
                      </div>
                    );
                  })}
              </div>

              {/* Detail by axis */}
              {competitors.length > 0 && (
                <div className="mt-6 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 pr-4 text-xs font-semibold text-muted-foreground">Concurrent</th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground">Total</th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground">Alignement</th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground">Fraicheur</th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground">Presence</th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground">Competitivite</th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground">Videos</th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground">Citations</th>
                      </tr>
                    </thead>
                    <tbody>
                      {score && (
                        <tr className="border-b border-border/50 bg-violet-50/50">
                          <td className="py-2.5 pr-4 font-bold text-violet-700">
                            Votre marque <span className="text-[9px] bg-violet-100 rounded px-1 py-0.5">vous</span>
                          </td>
                          <td className="text-center py-2.5 px-3 font-bold text-violet-700">{score.total}</td>
                          <td className="text-center py-2.5 px-3">{score.alignment}</td>
                          <td className="text-center py-2.5 px-3">{score.freshness}</td>
                          <td className="text-center py-2.5 px-3">{score.presence}</td>
                          <td className="text-center py-2.5 px-3">{score.competitivity}</td>
                          <td className="text-center py-2.5 px-3">{brandChannel?.video_count || 0}</td>
                          <td className="text-center py-2.5 px-3">-</td>
                        </tr>
                      )}
                      {competitors.map((c: any, i: number) => (
                        <tr key={i} className="border-b border-border/50 hover:bg-muted/30">
                          <td className="py-2.5 pr-4 font-medium text-foreground">{c.name}</td>
                          <td className="text-center py-2.5 px-3 font-semibold">{c.score?.total || 0}</td>
                          <td className="text-center py-2.5 px-3">{c.score?.alignment || 0}</td>
                          <td className="text-center py-2.5 px-3">{c.score?.freshness || 0}</td>
                          <td className="text-center py-2.5 px-3">{c.score?.presence || 0}</td>
                          <td className="text-center py-2.5 px-3">{c.score?.competitivity || 0}</td>
                          <td className="text-center py-2.5 px-3">{c.video_count || 0}</td>
                          <td className="text-center py-2.5 px-3">{c.citations || 0}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* ── Section 5: Diagnostic IA ── */}
          {diagnostic && (
            <div className="rounded-2xl border border-violet-200 bg-gradient-to-br from-violet-50 to-indigo-50 p-6 space-y-5">
              <h2 className="text-base font-semibold text-violet-800 flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                Diagnostic IA — Strategie VGEO
              </h2>
              <p className="text-sm text-violet-900 leading-relaxed">{diagnostic}</p>

              {/* Forces & Faiblesses */}
              {(forces.length > 0 || faiblesses.length > 0) && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {forces.length > 0 && (
                    <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4">
                      <h3 className="text-xs font-semibold text-emerald-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <CheckCircle2 className="h-3.5 w-3.5" /> Forces
                      </h3>
                      <ul className="space-y-1.5">
                        {forces.map((f: string, i: number) => (
                          <li key={i} className="text-xs text-emerald-800 flex items-start gap-1.5">
                            <span className="shrink-0 mt-0.5">+</span> {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {faiblesses.length > 0 && (
                    <div className="rounded-xl bg-red-50 border border-red-200 p-4">
                      <h3 className="text-xs font-semibold text-red-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                        <XCircle className="h-3.5 w-3.5" /> Faiblesses
                      </h3>
                      <ul className="space-y-1.5">
                        {faiblesses.map((f: string, i: number) => (
                          <li key={i} className="text-xs text-red-800 flex items-start gap-1.5">
                            <span className="shrink-0 mt-0.5">-</span> {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {/* Strategy priorities */}
              {strategy.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-violet-700 uppercase tracking-wider mb-3">Priorites strategiques</h3>
                  <div className="space-y-2">
                    {strategy.map((s: any, i: number) => (
                      <div key={i} className="rounded-xl bg-white/80 border border-violet-100 p-4">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-semibold text-violet-900">{s.action}</span>
                          <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                            s.impact === "high" ? "bg-red-100 text-red-700" : s.impact === "medium" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-600"
                          }`}>Impact {s.impact}</span>
                          <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                            s.effort === "low" ? "bg-green-100 text-green-700" : s.effort === "medium" ? "bg-amber-100 text-amber-700" : "bg-red-100 text-red-700"
                          }`}>Effort {s.effort}</span>
                        </div>
                        <p className="text-xs text-violet-800/80">{s.detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Section 6: Actions recommandees ── */}
          {actions.length > 0 && (
            <div className="rounded-2xl border border-border bg-card p-6">
              <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
                <Zap className="h-4 w-4 text-amber-500" />
                Actions recommandees
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {actions.map((a: any, i: number) => {
                  const priorityConfig: Record<string, { bg: string; text: string; border: string; label: string }> = {
                    quick_win: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200", label: "Quick Win" },
                    moyen_terme: { bg: "bg-blue-50", text: "text-blue-700", border: "border-blue-200", label: "Moyen terme" },
                    long_terme: { bg: "bg-purple-50", text: "text-purple-700", border: "border-purple-200", label: "Long terme" },
                  };
                  const cfg = priorityConfig[a.priority] || priorityConfig.moyen_terme;
                  return (
                    <div key={i} className={`rounded-xl border ${cfg.border} ${cfg.bg} p-4`}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${cfg.text} bg-white/60 border ${cfg.border}`}>
                          {cfg.label}
                        </span>
                      </div>
                      <h4 className="text-sm font-semibold text-foreground mb-1">{a.title}</h4>
                      <p className="text-xs text-muted-foreground">{a.description}</p>
                      {a.impact_estimate && (
                        <p className="text-[10px] text-violet-600 mt-2 font-medium">
                          Impact estime : {a.impact_estimate}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------
function VGeoHeader({ handleAnalyze, analyzing }: { handleAnalyze: () => void; analyzing: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-200/50">
          <Youtube className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">VGEO — Video GEO</h1>
          <p className="text-sm text-muted-foreground">
            Optimisez votre YouTube pour les moteurs IA
          </p>
        </div>
      </div>
      <button
        onClick={handleAnalyze}
        disabled={analyzing}
        className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-200/50 hover:shadow-xl hover:shadow-violet-300/50 transition-all disabled:opacity-50"
      >
        <RefreshCw className={`h-4 w-4 ${analyzing ? "animate-spin" : ""}`} />
        {analyzing ? "Analyse en cours..." : "Nouvelle analyse"}
      </button>
    </div>
  );
}
