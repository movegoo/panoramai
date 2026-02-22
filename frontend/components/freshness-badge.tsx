"use client";

import { Clock } from "lucide-react";

function formatRelativeTime(ts: string): string {
  const now = Date.now();
  const then = new Date(ts).getTime();
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "à l'instant";
  if (diffMin < 60) return `il y a ${diffMin}min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `il y a ${diffH}h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return "il y a 1j";
  if (diffD < 30) return `il y a ${diffD}j`;
  const diffM = Math.floor(diffD / 30);
  return `il y a ${diffM} mois`;
}

function getColor(ts: string): { dot: string; text: string } {
  const now = Date.now();
  const then = new Date(ts).getTime();
  const diffH = (now - then) / 3600000;
  if (diffH < 24) return { dot: "bg-emerald-500", text: "text-emerald-600" };
  if (diffH < 72) return { dot: "bg-amber-500", text: "text-amber-600" };
  return { dot: "bg-red-500", text: "text-red-600" };
}

export function FreshnessBadge({
  timestamp,
  label,
}: {
  timestamp: string | null | undefined;
  label?: string;
}) {
  if (!timestamp) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-gray-400">
        <span className="h-1.5 w-1.5 rounded-full bg-gray-300" />
        {label ? `${label} : ` : ""}Pas de données
      </span>
    );
  }

  const { dot, text } = getColor(timestamp);
  const relative = formatRelativeTime(timestamp);

  return (
    <span className={`inline-flex items-center gap-1 text-[11px] ${text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label ? `${label} : ` : ""}
      <Clock className="h-3 w-3" />
      {relative}
    </span>
  );
}

export function FreshnessBar({
  freshness,
}: {
  freshness: Record<string, string | null> | undefined;
}) {
  if (!freshness) return null;

  const platforms: { key: string; label: string }[] = [
    { key: "instagram", label: "Instagram" },
    { key: "tiktok", label: "TikTok" },
    { key: "youtube", label: "YouTube" },
    { key: "playstore", label: "Play Store" },
    { key: "appstore", label: "App Store" },
    { key: "ads_meta", label: "Ads Meta" },
    { key: "ads_google", label: "Ads Google" },
    { key: "ads_snapchat", label: "Ads Snap" },
  ];

  // Find the overall latest timestamp
  const allTs = Object.values(freshness).filter(Boolean) as string[];
  const latest = allTs.length ? allTs.sort().reverse()[0] : null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <FreshnessBadge timestamp={latest} label="Dernière maj" />
      <span className="text-gray-300">|</span>
      {platforms.map(({ key, label }) => (
        <FreshnessBadge key={key} timestamp={freshness[key]} label={label} />
      ))}
    </div>
  );
}
