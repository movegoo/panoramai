"use client";

import { useState } from "react";
import { useAPI } from "@/lib/use-api";
import { signalsAPI, SignalItem, SignalSummary } from "@/lib/api";
import { formatNumber, getRelativeTime } from "@/lib/utils";
import {
  Bell,
  BellOff,
  AlertTriangle,
  AlertCircle,
  Info,
  CheckCircle2,
  Filter,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Eye,
  EyeOff,
  Zap,
  Instagram,
  Youtube,
  Music,
  Smartphone,
  Megaphone,
  Globe,
  ChevronDown,
  Shield,
} from "lucide-react";

/* ─────────── Helpers ─────────── */

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; icon: typeof AlertTriangle }> = {
  critical: {
    label: "Critique",
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    icon: AlertCircle,
  },
  warning: {
    label: "Attention",
    color: "text-amber-700",
    bg: "bg-amber-50",
    border: "border-amber-200",
    icon: AlertTriangle,
  },
  info: {
    label: "Info",
    color: "text-blue-700",
    bg: "bg-blue-50",
    border: "border-blue-200",
    icon: Info,
  },
};

const PLATFORM_CONFIG: Record<string, { label: string; icon: typeof Instagram }> = {
  instagram: { label: "Instagram", icon: Instagram },
  tiktok: { label: "TikTok", icon: Music },
  youtube: { label: "YouTube", icon: Youtube },
  playstore: { label: "Play Store", icon: Smartphone },
  appstore: { label: "App Store", icon: Smartphone },
  meta_ads: { label: "Meta Ads", icon: Megaphone },
  facebook: { label: "Facebook", icon: Globe },
  snapchat: { label: "Snapchat", icon: Megaphone },
};

function SeverityBadge({ severity }: { severity: string }) {
  const cfg = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.info;
  const Icon = cfg.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold ${cfg.bg} ${cfg.color} ${cfg.border} border`}>
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  );
}

function PlatformBadge({ platform }: { platform: string }) {
  const cfg = PLATFORM_CONFIG[platform] || { label: platform, icon: Globe };
  const Icon = cfg.icon;
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-gray-100 text-gray-600 border border-gray-200">
      <Icon className="h-3 w-3" />
      {cfg.label}
    </span>
  );
}

function ChangeIndicator({ change, previous, current }: { change: number | null; previous: number | null; current: number | null }) {
  if (change === null || change === 0) return null;
  const isUp = change > 0;
  return (
    <div className="flex items-center gap-1.5 text-xs">
      {isUp ? (
        <TrendingUp className="h-3.5 w-3.5 text-emerald-500" />
      ) : (
        <TrendingDown className="h-3.5 w-3.5 text-red-500" />
      )}
      <span className={`font-semibold tabular-nums ${isUp ? "text-emerald-600" : "text-red-600"}`}>
        {change > 0 ? "+" : ""}{change.toFixed(1)}%
      </span>
      {previous !== null && current !== null && (
        <span className="text-muted-foreground">
          {formatNumber(previous)} &rarr; {formatNumber(current)}
        </span>
      )}
    </div>
  );
}

/* ─────────── Main Page ─────────── */

export default function SignalsPage() {
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);
  const [platformFilter, setPlatformFilter] = useState<string | null>(null);
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);
  const [detecting, setDetecting] = useState(false);

  // SWR queries
  const { data: signals, mutate: refreshSignals, isLoading: loadingSignals } = useAPI<SignalItem[]>(
    `/signals/?limit=100${severityFilter ? `&severity=${severityFilter}` : ""}${platformFilter ? `&platform=${platformFilter}` : ""}${showUnreadOnly ? "&unread_only=true" : ""}`
  );
  const { data: summary, mutate: refreshSummary } = useAPI<SignalSummary>("/signals/summary");

  const handleDetect = async () => {
    setDetecting(true);
    try {
      await signalsAPI.detect();
      refreshSignals();
      refreshSummary();
    } catch (e) {
      console.error("Detection failed:", e);
    } finally {
      setDetecting(false);
    }
  };

  const handleMarkRead = async (id: number) => {
    await signalsAPI.markRead(id);
    refreshSignals();
    refreshSummary();
  };

  const handleMarkAllRead = async () => {
    await signalsAPI.markAllRead();
    refreshSignals();
    refreshSummary();
  };

  const signalsList = signals || [];
  const total = summary?.total || 0;
  const unread = summary?.unread || 0;
  const bySeverity = summary?.by_severity || {};
  const byPlatform = summary?.by_platform || {};

  const platformKeys = Object.keys(byPlatform).sort((a, b) => byPlatform[b] - byPlatform[a]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Bell className="h-6 w-6 text-violet-600" />
            Signaux & Alertes
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Anomalies, tendances et mouvements concurrentiels detectes automatiquement
          </p>
        </div>
        <div className="flex items-center gap-2">
          {unread > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Tout marquer lu
            </button>
          )}
          <button
            onClick={handleDetect}
            disabled={detecting}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${detecting ? "animate-spin" : ""}`} />
            {detecting ? "Detection..." : "Lancer la detection"}
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">Total signaux</span>
            <Bell className="h-4 w-4 text-gray-400" />
          </div>
          <p className="text-2xl font-bold mt-1">{total}</p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">Non lus</span>
            <BellOff className="h-4 w-4 text-violet-500" />
          </div>
          <p className="text-2xl font-bold mt-1 text-violet-600">{unread}</p>
        </div>
        <div className="rounded-xl border border-red-100 bg-red-50/50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-red-600">Critiques</span>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </div>
          <p className="text-2xl font-bold mt-1 text-red-700">{bySeverity.critical || 0}</p>
        </div>
        <div className="rounded-xl border border-amber-100 bg-amber-50/50 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-amber-600">Attention</span>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </div>
          <p className="text-2xl font-bold mt-1 text-amber-700">{bySeverity.warning || 0}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
          <Filter className="h-3.5 w-3.5" /> Filtres:
        </span>

        {/* Severity filter */}
        {["critical", "warning", "info"].map((sev) => {
          const cfg = SEVERITY_CONFIG[sev];
          const active = severityFilter === sev;
          return (
            <button
              key={sev}
              onClick={() => setSeverityFilter(active ? null : sev)}
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
                active
                  ? `${cfg.bg} ${cfg.color} ${cfg.border}`
                  : "border-gray-200 text-gray-500 hover:bg-gray-50"
              }`}
            >
              {cfg.label}
              {bySeverity[sev] ? ` (${bySeverity[sev]})` : ""}
            </button>
          );
        })}

        <div className="w-px h-4 bg-gray-200" />

        {/* Platform filter */}
        {platformKeys.map((plat) => {
          const cfg = PLATFORM_CONFIG[plat] || { label: plat, icon: Globe };
          const Icon = cfg.icon;
          const active = platformFilter === plat;
          return (
            <button
              key={plat}
              onClick={() => setPlatformFilter(active ? null : plat)}
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
                active
                  ? "border-violet-300 bg-violet-50 text-violet-700"
                  : "border-gray-200 text-gray-500 hover:bg-gray-50"
              }`}
            >
              <Icon className="h-3 w-3" />
              {cfg.label} ({byPlatform[plat]})
            </button>
          );
        })}

        <div className="w-px h-4 bg-gray-200" />

        {/* Unread toggle */}
        <button
          onClick={() => setShowUnreadOnly(!showUnreadOnly)}
          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-colors ${
            showUnreadOnly
              ? "border-violet-300 bg-violet-50 text-violet-700"
              : "border-gray-200 text-gray-500 hover:bg-gray-50"
          }`}
        >
          {showUnreadOnly ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
          Non lus uniquement
        </button>
      </div>

      {/* Signals list */}
      <div className="space-y-2">
        {loadingSignals && signalsList.length === 0 && (
          <div className="flex items-center justify-center py-16">
            <div className="h-6 w-6 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          </div>
        )}

        {!loadingSignals && signalsList.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100 mb-4">
              <Bell className="h-7 w-7 text-gray-400" />
            </div>
            <h3 className="text-sm font-semibold text-foreground">Aucun signal detecte</h3>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">
              Lancez la detection pour analyser les dernieres variations de vos concurrents
            </p>
          </div>
        )}

        {signalsList.map((signal) => {
          const sevCfg = SEVERITY_CONFIG[signal.severity] || SEVERITY_CONFIG.info;
          return (
            <div
              key={signal.id}
              className={`rounded-xl border p-4 transition-all ${
                signal.is_brand
                  ? "border-violet-200 bg-violet-50/30 ring-1 ring-violet-100"
                  : signal.is_read
                    ? "border-gray-100 bg-white/50 opacity-70"
                    : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <div className="flex items-start gap-3">
                {/* Severity dot */}
                <div className={`mt-1 h-2.5 w-2.5 rounded-full shrink-0 ${
                  signal.severity === "critical" ? "bg-red-500" :
                  signal.severity === "warning" ? "bg-amber-500" : "bg-blue-500"
                }`} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {signal.is_brand && (
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-violet-100 text-violet-700 border border-violet-200">
                        <Shield className="h-2.5 w-2.5" /> VOUS
                      </span>
                    )}
                    <SeverityBadge severity={signal.severity} />
                    <PlatformBadge platform={signal.platform} />
                    <span className="text-[11px] text-muted-foreground ml-auto shrink-0">
                      {signal.detected_at ? getRelativeTime(signal.detected_at) : ""}
                    </span>
                  </div>

                  <h3 className={`text-sm font-semibold mt-1.5 ${signal.is_brand ? "text-violet-900" : "text-foreground"}`}>
                    {signal.title}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-0.5">{signal.description}</p>

                  <div className="flex items-center justify-between mt-2">
                    <ChangeIndicator
                      change={signal.change_percent}
                      previous={signal.previous_value}
                      current={signal.current_value}
                    />

                    {!signal.is_read && (
                      <button
                        onClick={() => handleMarkRead(signal.id)}
                        className="text-[11px] text-muted-foreground hover:text-violet-600 transition-colors flex items-center gap-1"
                      >
                        <CheckCircle2 className="h-3 w-3" />
                        Marquer lu
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
