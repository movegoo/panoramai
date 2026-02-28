"use client";

import { useState } from "react";
import { useAPI } from "@/lib/use-api";
import {
  EReputationDashboard,
  EReputationComment,
  EReputationCompetitorDetail,
  EReputationCommentList,
  eReputationAPI,
} from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { StatCard } from "@/components/stat-card";
import { LoadingState } from "@/components/loading-state";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import {
  Star,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  Minus,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Filter,
  Lightbulb,
  Shield,
  HeartHandshake,
  Youtube,
  Instagram,
  Music,
  ExternalLink,
  MessageSquareWarning,
} from "lucide-react";

const PLATFORM_ICONS: Record<string, typeof Youtube> = {
  youtube: Youtube,
  instagram: Instagram,
  tiktok: Music,
};

const PLATFORM_COLORS: Record<string, string> = {
  youtube: "text-red-600",
  instagram: "text-pink-600",
  tiktok: "text-gray-800",
};

const SENTIMENT_CONFIG: Record<string, { label: string; color: string; bg: string; icon: typeof ThumbsUp }> = {
  positive: { label: "Positif", color: "text-green-700", bg: "bg-green-50", icon: ThumbsUp },
  negative: { label: "Negatif", color: "text-red-700", bg: "bg-red-50", icon: ThumbsDown },
  neutral: { label: "Neutre", color: "text-gray-600", bg: "bg-gray-50", icon: Minus },
};

function ScoreGauge({ score, size = "lg" }: { score: number; size?: "sm" | "lg" }) {
  const color = score >= 70 ? "text-green-600" : score >= 40 ? "text-amber-500" : "text-red-600";
  const bgColor = score >= 70 ? "bg-green-50" : score >= 40 ? "bg-amber-50" : "bg-red-50";
  const sizeClass = size === "lg" ? "h-20 w-20 text-2xl" : "h-12 w-12 text-sm";
  return (
    <div className={`${sizeClass} ${bgColor} rounded-full flex items-center justify-center font-bold ${color} border-2 ${score >= 70 ? "border-green-200" : score >= 40 ? "border-amber-200" : "border-red-200"}`}>
      {Math.round(score)}
    </div>
  );
}

function SentimentDonut({ breakdown }: { breakdown: { positive: number; negative: number; neutral: number } }) {
  const total = breakdown.positive + breakdown.negative + breakdown.neutral;
  if (total === 0) return <div className="text-xs text-muted-foreground">Aucune donnee</div>;
  const pct = {
    positive: Math.round((breakdown.positive / total) * 100),
    negative: Math.round((breakdown.negative / total) * 100),
    neutral: Math.round((breakdown.neutral / total) * 100),
  };

  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1 h-3 w-24 rounded-full overflow-hidden">
        <div className="bg-green-500 transition-all" style={{ width: `${pct.positive}%` }} />
        <div className="bg-gray-300 transition-all" style={{ width: `${pct.neutral}%` }} />
        <div className="bg-red-500 transition-all" style={{ width: `${pct.negative}%` }} />
      </div>
      <div className="flex gap-2 text-[11px]">
        <span className="text-green-600 font-medium">{pct.positive}%</span>
        <span className="text-gray-500">{pct.neutral}%</span>
        <span className="text-red-600 font-medium">{pct.negative}%</span>
      </div>
    </div>
  );
}

function CommentCard({ comment }: { comment: EReputationComment }) {
  const sentimentCfg = SENTIMENT_CONFIG[comment.sentiment] || SENTIMENT_CONFIG.neutral;
  const PlatformIcon = PLATFORM_ICONS[comment.platform] || MessageSquare;
  const platformColor = PLATFORM_COLORS[comment.platform] || "text-gray-500";

  return (
    <div className={`p-3 rounded-lg border ${comment.is_alert ? "border-red-200 bg-red-50/50" : "border-border bg-card"}`}>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <PlatformIcon className={`h-3.5 w-3.5 shrink-0 ${platformColor}`} />
          <span className="text-xs font-medium text-foreground truncate">{comment.author || "Anonyme"}</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${sentimentCfg.bg} ${sentimentCfg.color} font-medium`}>
            {sentimentCfg.label}
          </span>
          {comment.is_alert && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 font-medium flex items-center gap-0.5">
              <AlertTriangle className="h-2.5 w-2.5" /> Alerte
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-[10px] text-muted-foreground shrink-0">
          {comment.likes > 0 && <span>{comment.likes} likes</span>}
          <span className="uppercase">{comment.source_type}</span>
        </div>
      </div>
      <p className="text-xs text-muted-foreground line-clamp-3">{comment.text}</p>
      {comment.is_alert && comment.alert_reason && (
        <p className="text-[10px] text-red-600 mt-1 font-medium">{comment.alert_reason}</p>
      )}
      {comment.source_title && (
        <div className="mt-1.5 flex items-center gap-1 text-[10px] text-muted-foreground/70">
          <ExternalLink className="h-2.5 w-2.5" />
          <span className="truncate">{comment.source_title}</span>
        </div>
      )}
    </div>
  );
}

export default function EReputationPage() {
  const { data: dashboard, isLoading } = useAPI<EReputationDashboard>("/ereputation/dashboard");
  const [selectedCompetitor, setSelectedCompetitor] = useState<number | null>(null);
  const [view, setView] = useState<"dashboard" | "detail" | "comments">("dashboard");
  const [commentFilters, setCommentFilters] = useState<{
    platform?: string;
    sentiment?: string;
    source_type?: string;
    page: number;
  }>({ page: 1 });
  const [auditing, setAuditing] = useState(false);

  const { data: detail } = useAPI<EReputationCompetitorDetail>(
    selectedCompetitor && view === "detail" ? `/ereputation/competitor/${selectedCompetitor}` : null
  );

  const commentParams = new URLSearchParams();
  if (commentFilters.platform) commentParams.set("platform", commentFilters.platform);
  if (commentFilters.sentiment) commentParams.set("sentiment", commentFilters.sentiment);
  if (commentFilters.source_type) commentParams.set("source_type", commentFilters.source_type);
  if (selectedCompetitor && view === "comments") commentParams.set("competitor_id", String(selectedCompetitor));
  commentParams.set("page", String(commentFilters.page));
  const commentQs = commentParams.toString();

  const { data: commentsList } = useAPI<EReputationCommentList>(
    view === "comments" ? `/ereputation/comments?${commentQs}` : null
  );

  const { data: alerts } = useAPI<{ alerts: EReputationComment[]; total: number }>("/ereputation/alerts");

  async function handleRunAudit() {
    setAuditing(true);
    try {
      await eReputationAPI.runAudit();
    } catch {}
    setAuditing(false);
  }

  if (isLoading) return <LoadingState message="Chargement e-reputation..." />;

  const competitors = dashboard?.competitors || [];
  const summary = dashboard?.summary;

  // Detail view
  if (view === "detail" && selectedCompetitor) {
    const comp = competitors.find((c) => c.competitor_id === selectedCompetitor);
    const audit = detail?.audit;

    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <button onClick={() => { setView("dashboard"); setSelectedCompetitor(null); }} className="text-muted-foreground hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <PageHeader icon={MessageSquareWarning} title={`E-Reputation : ${comp?.competitor_name || ""}`} />
        </div>

        {!audit ? (
          <EmptyState title="Aucun audit" description="Lancez un audit pour analyser la reputation de ce concurrent." />
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Score Reputation" value={`${audit.reputation_score}/100`} icon={Star} />
              <StatCard label="NPS" value={audit.nps > 0 ? `+${audit.nps}` : String(audit.nps)} icon={audit.nps >= 0 ? TrendingUp : TrendingDown} />
              <StatCard label="Taux SAV" value={`${audit.sav_rate}%`} icon={HeartHandshake} />
              <StatCard label="Risque Financier" value={`${audit.financial_risk_rate}%`} icon={Shield} />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Sentiment */}
              <div className="rounded-xl border border-border bg-card p-4">
                <h3 className="text-sm font-semibold mb-3">Sentiment</h3>
                <SentimentDonut breakdown={audit.sentiment_breakdown} />
                <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-lg bg-green-50 p-2">
                    <div className="font-bold text-green-700">{audit.sentiment_breakdown.positive}</div>
                    <div className="text-green-600">Positifs</div>
                  </div>
                  <div className="rounded-lg bg-gray-50 p-2">
                    <div className="font-bold text-gray-700">{audit.sentiment_breakdown.neutral}</div>
                    <div className="text-gray-500">Neutres</div>
                  </div>
                  <div className="rounded-lg bg-red-50 p-2">
                    <div className="font-bold text-red-700">{audit.sentiment_breakdown.negative}</div>
                    <div className="text-red-600">Negatifs</div>
                  </div>
                </div>
              </div>

              {/* Platforms */}
              <div className="rounded-xl border border-border bg-card p-4">
                <h3 className="text-sm font-semibold mb-3">Par plateforme</h3>
                <div className="space-y-2">
                  {Object.entries(audit.platform_breakdown).map(([platform, stats]) => {
                    const Icon = PLATFORM_ICONS[platform] || MessageSquare;
                    return (
                      <div key={platform} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <Icon className={`h-3.5 w-3.5 ${PLATFORM_COLORS[platform] || ""}`} />
                          <span className="capitalize font-medium">{platform}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-green-600">{stats.positive}</span>
                          <span className="text-gray-400">{stats.neutral}</span>
                          <span className="text-red-600">{stats.negative}</span>
                          <span className="text-muted-foreground">({stats.total})</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* AI Synthesis */}
            {audit.ai_synthesis && (audit.ai_synthesis.insights?.length > 0 || audit.ai_synthesis.recommendations?.length > 0) && (
              <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-violet-600" /> Synthese IA
                </h3>
                {audit.ai_synthesis.risk_summary && (
                  <p className="text-xs text-red-700 mb-2 p-2 bg-red-50 rounded-lg">{audit.ai_synthesis.risk_summary}</p>
                )}
                {audit.ai_synthesis.strength_summary && (
                  <p className="text-xs text-green-700 mb-2 p-2 bg-green-50 rounded-lg">{audit.ai_synthesis.strength_summary}</p>
                )}
                {audit.ai_synthesis.insights?.length > 0 && (
                  <div className="mb-3">
                    <h4 className="text-xs font-semibold text-violet-700 mb-1">Insights</h4>
                    <ul className="space-y-1">
                      {audit.ai_synthesis.insights.map((insight, i) => (
                        <li key={i} className="text-xs text-muted-foreground flex gap-2">
                          <span className="text-violet-500 shrink-0">-</span> {insight}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {audit.ai_synthesis.recommendations?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-violet-700 mb-1">Recommandations</h4>
                    <ul className="space-y-1">
                      {audit.ai_synthesis.recommendations.map((rec, i) => (
                        <li key={i} className="text-xs text-muted-foreground flex gap-2">
                          <span className="text-violet-500 shrink-0">-</span> {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Alerts */}
            {(detail?.alerts?.length || 0) > 0 && (
              <div className="rounded-xl border border-red-200 bg-red-50/30 p-4">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-red-700">
                  <AlertTriangle className="h-4 w-4" /> Alertes ({detail!.alerts.length})
                </h3>
                <div className="space-y-2">
                  {detail!.alerts.slice(0, 10).map((a) => (
                    <CommentCard key={a.id} comment={a} />
                  ))}
                </div>
              </div>
            )}

            {/* Recent comments */}
            {(detail?.comments?.length || 0) > 0 && (
              <div className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold">Commentaires ({detail!.comments.length})</h3>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setView("comments")}
                    className="text-xs"
                  >
                    Voir tout <ChevronRight className="h-3 w-3 ml-1" />
                  </Button>
                </div>
                <div className="space-y-2">
                  {detail!.comments.slice(0, 20).map((c) => (
                    <CommentCard key={c.id} comment={c} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    );
  }

  // Comments explorer view
  if (view === "comments") {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <button onClick={() => { setView(selectedCompetitor ? "detail" : "dashboard"); setCommentFilters({ page: 1 }); }} className="text-muted-foreground hover:text-foreground">
            <ChevronLeft className="h-5 w-5" />
          </button>
          <PageHeader icon={MessageSquareWarning} title="Explorateur de commentaires" />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2">
          <select
            className="text-xs border rounded-lg px-2 py-1.5 bg-card"
            value={commentFilters.platform || ""}
            onChange={(e) => setCommentFilters({ ...commentFilters, platform: e.target.value || undefined, page: 1 })}
          >
            <option value="">Toutes les plateformes</option>
            <option value="youtube">YouTube</option>
            <option value="tiktok">TikTok</option>
            <option value="instagram">Instagram</option>
          </select>
          <select
            className="text-xs border rounded-lg px-2 py-1.5 bg-card"
            value={commentFilters.sentiment || ""}
            onChange={(e) => setCommentFilters({ ...commentFilters, sentiment: e.target.value || undefined, page: 1 })}
          >
            <option value="">Tous les sentiments</option>
            <option value="positive">Positif</option>
            <option value="negative">Negatif</option>
            <option value="neutral">Neutre</option>
          </select>
          <select
            className="text-xs border rounded-lg px-2 py-1.5 bg-card"
            value={commentFilters.source_type || ""}
            onChange={(e) => setCommentFilters({ ...commentFilters, source_type: e.target.value || undefined, page: 1 })}
          >
            <option value="">Owned + Earned</option>
            <option value="owned">Owned</option>
            <option value="earned">Earned</option>
          </select>
        </div>

        {/* Comments list */}
        <div className="space-y-2">
          {commentsList?.comments?.map((c) => (
            <CommentCard key={c.id} comment={c} />
          ))}
          {(!commentsList?.comments || commentsList.comments.length === 0) && (
            <EmptyState title="Aucun commentaire" description="Aucun commentaire ne correspond aux filtres." />
          )}
        </div>

        {/* Pagination */}
        {commentsList && commentsList.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={commentFilters.page <= 1}
              onClick={() => setCommentFilters({ ...commentFilters, page: commentFilters.page - 1 })}
            >
              <ChevronLeft className="h-3 w-3" />
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {commentFilters.page} / {commentsList.total_pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={commentFilters.page >= commentsList.total_pages}
              onClick={() => setCommentFilters({ ...commentFilters, page: commentFilters.page + 1 })}
            >
              <ChevronRight className="h-3 w-3" />
            </Button>
          </div>
        )}
      </div>
    );
  }

  // Dashboard view (default)
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader
          icon={MessageSquareWarning}
          title="E-Reputation"
          subtitle="Analyse de la reputation en ligne de vos concurrents"
        />
        <Button
          onClick={handleRunAudit}
          disabled={auditing}
          size="sm"
          className="bg-violet-600 hover:bg-violet-700 text-white"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${auditing ? "animate-spin" : ""}`} />
          {auditing ? "Audit en cours..." : "Lancer un audit"}
        </Button>
      </div>

      {/* Summary KPIs */}
      {summary && summary.total_audited > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Score moyen" value={`${summary.avg_reputation_score}/100`} icon={Star} />
          <StatCard label="NPS moyen" value={summary.avg_nps > 0 ? `+${summary.avg_nps}` : String(summary.avg_nps)} icon={TrendingUp} />
          <StatCard label="Concurrents audites" value={String(summary.total_audited)} icon={MessageSquare} />
          <StatCard label="Alertes" value={String(summary.total_alerts)} icon={AlertTriangle} />
        </div>
      )}

      {/* Competitors table */}
      {competitors.length === 0 ? (
        <EmptyState
          title="Aucun concurrent"
          description="Ajoutez des concurrents pour commencer l'analyse e-reputation."
        />
      ) : (
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b bg-muted/30">
                <th className="text-left px-4 py-2.5 font-semibold">Concurrent</th>
                <th className="text-center px-3 py-2.5 font-semibold">Score</th>
                <th className="text-center px-3 py-2.5 font-semibold">NPS</th>
                <th className="text-center px-3 py-2.5 font-semibold hidden md:table-cell">Sentiment</th>
                <th className="text-center px-3 py-2.5 font-semibold hidden md:table-cell">Comments</th>
                <th className="text-center px-3 py-2.5 font-semibold hidden lg:table-cell">SAV</th>
                <th className="px-3 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {competitors
                .sort((a, b) => (b.audit?.reputation_score || 0) - (a.audit?.reputation_score || 0))
                .map((comp) => (
                  <tr key={comp.competitor_id} className="border-b last:border-0 hover:bg-muted/20 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        {comp.logo_url ? (
                          <img src={comp.logo_url} className="h-7 w-7 rounded-lg object-contain bg-white border" alt="" />
                        ) : (
                          <div className="h-7 w-7 rounded-lg bg-muted flex items-center justify-center text-[10px] font-bold">
                            {comp.competitor_name?.charAt(0)}
                          </div>
                        )}
                        <span className="font-medium">{comp.competitor_name}</span>
                      </div>
                    </td>
                    <td className="text-center px-3 py-3">
                      {comp.audit ? <ScoreGauge score={comp.audit.reputation_score} size="sm" /> : <span className="text-muted-foreground">-</span>}
                    </td>
                    <td className="text-center px-3 py-3">
                      {comp.audit ? (
                        <span className={`font-semibold ${comp.audit.nps >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {comp.audit.nps > 0 ? "+" : ""}{comp.audit.nps}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="text-center px-3 py-3 hidden md:table-cell">
                      {comp.audit ? <SentimentDonut breakdown={comp.audit.sentiment_breakdown} /> : <span className="text-muted-foreground">-</span>}
                    </td>
                    <td className="text-center px-3 py-3 hidden md:table-cell">
                      {comp.audit?.total_comments ?? "-"}
                    </td>
                    <td className="text-center px-3 py-3 hidden lg:table-cell">
                      {comp.audit ? (
                        <span className={comp.audit.sav_rate > 15 ? "text-red-600 font-medium" : "text-muted-foreground"}>
                          {comp.audit.sav_rate}%
                        </span>
                      ) : "-"}
                    </td>
                    <td className="px-3 py-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => { setSelectedCompetitor(comp.competitor_id); setView("detail"); }}
                        className="text-xs"
                      >
                        Detail <ChevronRight className="h-3 w-3 ml-0.5" />
                      </Button>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Alerts section */}
      {alerts && alerts.alerts.length > 0 && (
        <div className="rounded-xl border border-red-200 bg-red-50/30 p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2 text-red-700">
            <AlertTriangle className="h-4 w-4" /> Alertes recentes ({alerts.total})
          </h3>
          <div className="space-y-2">
            {alerts.alerts.slice(0, 5).map((a) => (
              <CommentCard key={a.id} comment={a} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
