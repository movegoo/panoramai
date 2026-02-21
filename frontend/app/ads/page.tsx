"use client";

import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { PieChart as RechartsPie, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from "recharts";
import { Button } from "@/components/ui/button";
import {
  competitorsAPI,
  facebookAPI,
  tiktokAPI,
  googleAdsAPI,
  brandAPI,
  creativeAPI,
  Ad,
  CreativeInsights,
} from "@/lib/api";
import { useAPI } from "@/lib/use-api";
import { formatDate, formatNumber } from "@/lib/utils";
import {
  RefreshCw,
  ExternalLink,
  ArrowUpRight,
  Zap,
  Eye,
  Globe,
  Users,
  ThumbsUp,
  Sparkles,
  Link2,
  Tag,
  Monitor,
  ChevronDown,
  ChevronUp,
  Filter,
  Calendar,
  BarChart3,
  Search,
  X,
  Building2,
  Layers,
  Play,
  Image,
  SlidersHorizontal,
  MapPin,
  UserCheck,
  Target,
  Shield,
  TrendingUp,
  PieChart,
  Megaphone,
  ImageOff,
  Radio,
  Brain,
  Palette,
  Trophy,
  Lightbulb,
  Loader2,
} from "lucide-react";
import { PeriodFilter, PeriodDays, DateRangeFilter } from "@/components/period-filter";

/* ─────────────── Platform icons (inline SVG) ─────────────── */

function FacebookIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
    </svg>
  );
}

function InstagramIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
    </svg>
  );
}

function MessengerIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12 0C5.373 0 0 4.974 0 11.111c0 3.498 1.744 6.614 4.469 8.654V24l4.088-2.242c1.092.3 2.246.464 3.443.464 6.627 0 12-4.975 12-11.111S18.627 0 12 0zm1.191 14.963l-3.055-3.26-5.963 3.26L10.732 8.2l3.131 3.259L19.752 8.2l-6.561 6.763z"/>
    </svg>
  );
}

function TikTokIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"/>
    </svg>
  );
}

function YouTubeIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
    </svg>
  );
}

function GooglePlayIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M3.609 1.814L13.792 12 3.61 22.186a.996.996 0 0 1-.61-.92V2.734a1 1 0 0 1 .609-.92zm10.89 10.893l2.302 2.302-10.937 6.333 8.635-8.635zm3.199-1.707l2.755 1.593a1 1 0 0 1 0 1.732l-2.755 1.593-2.534-2.534 2.534-2.384zM5.864 3.458L16.8 9.79l-2.302 2.302-8.634-8.634z"/>
    </svg>
  );
}

function AppStoreIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M8.809 14.92l6.11-11.037c.084-.152.12-.32.104-.487a.801.801 0 0 0-.312-.564.802.802 0 0 0-.629-.144.798.798 0 0 0-.512.372L7.38 14.92H2.498a.8.8 0 0 0 0 1.6h3.762l-2.534 4.576a.8.8 0 1 0 1.4.776l2.774-5.009h8.2l2.774 5.009a.8.8 0 1 0 1.4-.776l-2.534-4.576h3.762a.8.8 0 1 0 0-1.6H8.809zm4.798-8.652L17.21 14.92h-7.206l3.603-8.652z"/>
    </svg>
  );
}

function GoogleAdsIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M3.186 10.324l7.77-4.474 2.07 3.588-7.77 4.474zm14.358-6.312a3.012 3.012 0 0 0-4.122 1.1L7.91 14.998l4.122 2.378 5.512-9.542a3.012 3.012 0 0 0-1.1-4.122zM6.014 17.998a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"/>
    </svg>
  );
}

function MetaIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 36 36" className={className} fill="currentColor">
      <path d="M7.5 16.5c0-3.38 1.19-6.2 2.85-7.78C11.5 7.6 13 7.05 14.4 7.05c1.85 0 3.35.95 4.85 3.15l.75 1.1.75-1.1c1.5-2.2 3-3.15 4.85-3.15 1.4 0 2.9.55 4.05 1.67C31.31 10.3 32.5 13.12 32.5 16.5c0 5.52-5.58 12.45-14.5 12.45S3.5 22.02 3.5 16.5h4c0 3.25 3.75 8.45 10.5 8.45s10.5-5.2 10.5-8.45c0-2.36-.78-4.28-1.82-5.28-.55-.53-1.08-.72-1.58-.72-.8 0-1.55.55-2.6 2.1l-2.2 3.25c-.85 1.25-1.6 1.7-2.8 1.7-1.2 0-1.95-.45-2.8-1.7l-2.2-3.25c-1.05-1.55-1.8-2.1-2.6-2.1-.5 0-1.03.19-1.58.72C9.78 12.22 9 14.14 9 16.5H7.5z"/>
    </svg>
  );
}

/* ─────────────── CPM Benchmarks & Budget Estimation ─────────────── */

// CPM benchmarks by country (EUR) - Source: industry averages 2025-2026
// Google Display ~1-2€, Google Search ~10-15€ → blended ~4€ for awareness/display campaigns
const CPM_BENCHMARKS: Record<string, { meta: number; tiktok: number; google: number }> = {
  FR: { meta: 3.0, tiktok: 2.0, google: 1.0 },
  DE: { meta: 3.0, tiktok: 2.5, google: 1.0 },
  ES: { meta: 2.5, tiktok: 1.5, google: 1.0 },
  IT: { meta: 2.5, tiktok: 1.5, google: 1.0 },
  BE: { meta: 3.0, tiktok: 2.0, google: 1.0 },
  NL: { meta: 3.0, tiktok: 2.5, google: 1.0 },
  UK: { meta: 3.0, tiktok: 2.5, google: 1.0 },
  US: { meta: 3.0, tiktok: 2.5, google: 1.0 },
  DEFAULT: { meta: 3.0, tiktok: 2.0, google: 1.0 },
};

function estimateBudget(ad: AdWithCompetitor): { min: number; max: number; method: string } | null {
  // Priority 1: Declared spend from Meta
  if (ad.estimated_spend_min && ad.estimated_spend_min > 0) return null;

  // Determine platform CPM
  const source = normalizeSource(ad.platform);
  const country = ad.targeted_countries?.[0] || "FR";
  const benchmark = CPM_BENCHMARKS[country] || CPM_BENCHMARKS.DEFAULT;
  const cpm = (benchmark as Record<string, number>)[source] || benchmark.meta;

  // Priority 2: Impressions x CPM
  if (ad.impressions_min && ad.impressions_min > 0) {
    const minBudget = (ad.impressions_min / 1000) * cpm;
    const maxBudget = ad.impressions_max ? (ad.impressions_max / 1000) * cpm : minBudget * 1.3;
    return {
      min: Math.round(minBudget),
      max: Math.round(maxBudget),
      method: "impressions",
    };
  }

  // Priority 3: Reach x CPM (fallback)
  const reach = ad.eu_total_reach;
  if (!reach || reach < 100) return null;

  const estimated = (reach / 1000) * cpm;
  return {
    min: Math.round(estimated * 0.7),
    max: Math.round(estimated * 1.3),
    method: "reach",
  };
}

function getSourcePlatform(ad: AdWithCompetitor): { label: string; icon: React.ReactNode; color: string; bg: string } {
  if (ad.platform === "tiktok") {
    return { label: "TikTok Ads", icon: <TikTokIcon className="h-3.5 w-3.5" />, color: "text-slate-800", bg: "bg-slate-100 border-slate-200" };
  }
  if (ad.platform === "google") {
    return { label: "Google Ads", icon: <GoogleAdsIcon className="h-3.5 w-3.5" />, color: "text-amber-700", bg: "bg-amber-50 border-amber-200" };
  }
  // Default: Meta (Facebook Ad Library)
  return { label: "Meta Ads", icon: <MetaIcon className="h-3.5 w-3.5" />, color: "text-blue-600", bg: "bg-blue-50 border-blue-200" };
}

const SOURCE_CONFIG: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  meta: { label: "Meta", icon: <MetaIcon className="h-3 w-3" />, color: "#3b82f6" },
  tiktok: { label: "TikTok", icon: <TikTokIcon className="h-3 w-3" />, color: "#0f172a" },
  google: { label: "Google", icon: <GoogleAdsIcon className="h-3 w-3" />, color: "#f59e0b" },
};

function normalizeSource(platform: string | undefined | null): string {
  if (platform === "tiktok") return "tiktok";
  if (platform === "google") return "google";
  return "meta";
}

/** Get effective publisher platforms, falling back to platform field */
function getPublisherPlatforms(ad: { publisher_platforms?: string[]; platform?: string }): string[] {
  if (ad.publisher_platforms && ad.publisher_platforms.length > 0) return ad.publisher_platforms;
  // Fallback: derive from platform field
  if (ad.platform === "tiktok") return ["TIKTOK"];
  if (ad.platform === "google") return ["GOOGLE"];
  if (ad.platform === "instagram") return ["INSTAGRAM"];
  if (ad.platform === "facebook") return ["FACEBOOK"];
  return ["UNKNOWN"];
}

/* ─────────────── Gender normalization ─────────────── */

function normalizeGender(raw: string | undefined | null): "all" | "male" | "female" | null {
  if (!raw) return null;
  const v = raw.toLowerCase();
  if (v === "all" || v === "all genders") return "all";
  if (v === "male" || v === "men" || v === "homme" || v === "hommes") return "male";
  if (v === "female" || v === "women" || v === "femme" || v === "femmes") return "female";
  return null;
}

function genderLabel(raw: string | undefined | null): string {
  const n = normalizeGender(raw);
  if (n === "all") return "Mixte";
  if (n === "male") return "Hommes";
  if (n === "female") return "Femmes";
  return raw || "Inconnu";
}

/* ─────────────── Tooltip component ─────────────── */

function InfoTooltip({ text, className = "", light = false }: { text: string; className?: string; light?: boolean }) {
  const [show, setShow] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const handleEnter = () => {
    if (ref.current) {
      const r = ref.current.getBoundingClientRect();
      setPos({ top: r.top - 8, left: r.left + r.width / 2 });
    }
    setShow(true);
  };

  return (
    <span className={`inline-flex ${className}`}>
      <span
        ref={ref}
        onMouseEnter={handleEnter}
        onMouseLeave={() => setShow(false)}
        className={`${light ? "text-white/30 hover:text-white/70" : "text-muted-foreground/40 hover:text-muted-foreground"} transition-colors cursor-help`}
      >
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="currentColor">
          <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 12.5a5.5 5.5 0 110-11 5.5 5.5 0 010 11zM8 4.5a1 1 0 100 2 1 1 0 000-2zM7 8v3.5h2V8H7z"/>
        </svg>
      </span>
      {show && createPortal(
        <span
          className="fixed z-[9999] w-64 px-3 py-2 rounded-lg bg-gray-900 text-white text-[11px] leading-relaxed shadow-xl pointer-events-none"
          style={{ top: pos.top, left: pos.left, transform: "translate(-50%, -100%)" }}
        >
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </span>,
        document.body
      )}
    </span>
  );
}

/* ─────────────── Methodology texts ─────────────── */

const METHODOLOGY = {
  budget: "Budget estim\u00E9 : 1) Budget d\u00E9clar\u00E9 Meta si disponible, 2) Impressions x CPM, 3) Reach EU x CPM (fallback). CPM benchmarks FR : 3\u20AC Meta / 2\u20AC TikTok / 1\u20AC Google.",
  reach: "Couverture EU totale d\u00E9clar\u00E9e par Meta via l\u2019EU Ad Transparency Center. Nombre de personnes uniques ayant vu la pub dans l\u2019UE.",
  duration: "Dur\u00E9e moyenne = (date de fin - date de d\u00E9but) pour chaque pub termin\u00E9e. Les pubs encore actives (sans date de fin) sont exclues du calcul.",
  demographics: "Donn\u00E9es issues du Meta EU Ad Transparency Center. R\u00E9partition par \u00E2ge/genre/pays des personnes atteintes. Disponible uniquement pour les pubs Meta diffus\u00E9es dans l\u2019UE.",
  activeAds: "Une pub est consid\u00E9r\u00E9e active si elle a \u00E9t\u00E9 diffus\u00E9e dans les 7 derniers jours (Meta/Google) ou est marqu\u00E9e active par la plateforme.",
  platforms: "Plateformes de diffusion d\u00E9clar\u00E9es : Facebook, Instagram, Messenger, Audience Network (Meta), TikTok Ads, Google Ads Transparency Center.",
  formats: "Format cr\u00E9atif : VIDEO (vid\u00E9o), IMAGE (statique), DCO (multi-cr\u00E9atif dynamique), CAROUSEL (carrousel), DPA (catalogue produit).",
  gender: "Ciblage genre d\u00E9clar\u00E9 par l\u2019annonceur via Meta. \u00AB Mixte \u00BB = aucun ciblage genre sp\u00E9cifique.",
  googleAds: "Pubs collect\u00E9es via le Google Ads Transparency Center. Pas de donn\u00E9es d\u00E9mographiques disponibles (uniquement Meta).",
};

/* ─────────────── Constants ─────────────── */

const PLATFORM_CONFIGS: Record<string, { label: string; color: string; iconColor: string; bg: string }> = {
  FACEBOOK: { label: "Facebook", color: "bg-blue-100 text-blue-700 border-blue-200", iconColor: "text-blue-600", bg: "bg-blue-500" },
  INSTAGRAM: { label: "Instagram", color: "bg-gradient-to-r from-pink-100 to-purple-100 text-pink-700 border-pink-200", iconColor: "text-pink-600", bg: "bg-gradient-to-r from-pink-500 to-purple-500" },
  AUDIENCE_NETWORK: { label: "Audience Network", color: "bg-teal-100 text-teal-700 border-teal-200", iconColor: "text-teal-600", bg: "bg-teal-500" },
  MESSENGER: { label: "Messenger", color: "bg-violet-100 text-violet-700 border-violet-200", iconColor: "text-violet-600", bg: "bg-violet-500" },
  THREADS: { label: "Threads", color: "bg-stone-100 text-stone-700 border-stone-200", iconColor: "text-stone-600", bg: "bg-stone-500" },
  TIKTOK: { label: "TikTok", color: "bg-slate-100 text-slate-800 border-slate-200", iconColor: "text-slate-800", bg: "bg-slate-800" },
  GOOGLE: { label: "Google", color: "bg-amber-100 text-amber-700 border-amber-200", iconColor: "text-amber-600", bg: "bg-amber-500" },
  YOUTUBE: { label: "YouTube", color: "bg-red-100 text-red-700 border-red-200", iconColor: "text-red-600", bg: "bg-red-500" },
  GOOGLE_PLAY: { label: "Google Play", color: "bg-green-100 text-green-700 border-green-200", iconColor: "text-green-600", bg: "bg-green-500" },
  APP_STORE: { label: "App Store", color: "bg-sky-100 text-sky-700 border-sky-200", iconColor: "text-sky-600", bg: "bg-sky-500" },
};

const FORMAT_LABELS: Record<string, { label: string; icon: string }> = {
  VIDEO: { label: "Video", icon: "play" },
  IMAGE: { label: "Image", icon: "image" },
  DCO: { label: "Multi-creative", icon: "layers" },
  CAROUSEL: { label: "Carrousel", icon: "layers" },
  DPA: { label: "Catalogue", icon: "layers" },
};

const AGE_ORDER = ["13-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"];

const COUNTRY_LABELS: Record<string, string> = {
  FR: "France", ES: "Espagne", IT: "Italie", DE: "Allemagne", PT: "Portugal",
  BE: "Belgique", NL: "Pays-Bas", PL: "Pologne", RO: "Roumanie", CH: "Suisse",
  AT: "Autriche", GB: "Royaume-Uni", US: "Etats-Unis", BR: "Bresil",
};

type AdWithCompetitor = Ad & { competitor_name: string };

/* ─────────────── Sub-components ─────────────── */

function PlatformIcon({ name, className = "h-3.5 w-3.5" }: { name: string; className?: string }) {
  switch (name) {
    case "FACEBOOK": return <FacebookIcon className={className} />;
    case "INSTAGRAM": return <InstagramIcon className={className} />;
    case "MESSENGER": return <MessengerIcon className={className} />;
    case "TIKTOK": return <TikTokIcon className={className} />;
    case "GOOGLE": return <GoogleAdsIcon className={className} />;
    case "YOUTUBE": return <YouTubeIcon className={className} />;
    case "GOOGLE_PLAY": case "PLAYSTORE": return <GooglePlayIcon className={className} />;
    case "APP_STORE": case "APPSTORE": return <AppStoreIcon className={className} />;
    default: return <Globe className={className} />;
  }
}

function PlatformPill({ name }: { name: string }) {
  const config = PLATFORM_CONFIGS[name];
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${config?.color || "bg-gray-100 text-gray-600 border-gray-200"}`}>
      <PlatformIcon name={name} className="h-3 w-3" />
      {config?.label || name.toLowerCase().replace("_", " ")}
    </span>
  );
}

function FilterChip({ label, active, onClick, count, icon }: { label: string; active: boolean; onClick: () => void; count?: number; icon?: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
        active
          ? "bg-foreground text-background shadow-sm"
          : "bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground"
      }`}
    >
      {icon}
      {label}
      {count !== undefined && (
        <span className={`text-[10px] tabular-nums ${active ? "text-background/70" : "text-muted-foreground/60"}`}>
          {count}
        </span>
      )}
    </button>
  );
}

function AdvertiserAvatar({ ad, size = "sm", logoUrl }: { ad: AdWithCompetitor; size?: "sm" | "md" | "lg"; logoUrl?: string }) {
  const sizeClasses = { sm: "h-6 w-6", md: "h-8 w-8", lg: "h-10 w-10" };
  const textSizes = { sm: "text-[9px]", md: "text-[10px]", lg: "text-xs" };
  const imgSrc = logoUrl;
  if (imgSrc) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={imgSrc} alt="" className={`${sizeClasses[size]} rounded-full object-cover border-2 border-background shrink-0`} />
    );
  }
  const initials = (ad.page_name || ad.competitor_name || "?").slice(0, 2).toUpperCase();
  return (
    <div className={`${sizeClasses[size]} rounded-full bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center shrink-0 border-2 border-background`}>
      <span className={`${textSizes[size]} font-bold text-slate-600`}>{initials}</span>
    </div>
  );
}

function GenderBar({ male, female, unknown, compact = false }: { male: number; female: number; unknown: number; compact?: boolean }) {
  const total = male + female + unknown;
  if (total === 0) return null;
  const malePct = Math.round((male / total) * 100);
  const femalePct = Math.round((female / total) * 100);
  const unknownPct = 100 - malePct - femalePct;
  return (
    <div>
      <div className={`flex rounded-full overflow-hidden ${compact ? "h-2" : "h-3"}`}>
        <div className="bg-blue-500 transition-all" style={{ width: `${malePct}%` }} title={`Hommes: ${malePct}%`} />
        <div className="bg-pink-500 transition-all" style={{ width: `${femalePct}%` }} title={`Femmes: ${femalePct}%`} />
        {unknownPct > 0 && <div className="bg-gray-300 transition-all" style={{ width: `${unknownPct}%` }} title={`Inconnu: ${unknownPct}%`} />}
      </div>
      {!compact && (
        <div className="flex items-center justify-between mt-1">
          <span className="text-[10px] text-blue-600 font-semibold tabular-nums">{malePct}% H</span>
          <span className="text-[10px] text-pink-600 font-semibold tabular-nums">{femalePct}% F</span>
          {unknownPct > 1 && <span className="text-[10px] text-gray-400 font-semibold tabular-nums">{unknownPct}%</span>}
        </div>
      )}
    </div>
  );
}

function AdCard({ ad, expanded, onToggle, advertiserLogo, brandName }: { ad: AdWithCompetitor; expanded: boolean; onToggle: () => void; advertiserLogo?: string; brandName?: string }) {
  const isBrand = !!(brandName && ad.competitor_name?.toLowerCase() === brandName.toLowerCase());
  const durationDays = (ad.start_date && ad.end_date) ? Math.ceil((new Date(ad.end_date).getTime() - new Date(ad.start_date).getTime()) / 86400000) : 0;
  const [imgError, setImgError] = useState(false);
  const linkHref = ad.ad_library_url || ad.link_url || ad.creative_url;
  return (
    <div className={`group relative rounded-2xl border bg-card overflow-hidden transition-all duration-300 hover:shadow-xl hover:-translate-y-0.5 ${isBrand ? "bg-violet-50/50 ring-1 ring-violet-200" : ""}`}>
      {/* Image */}
      {ad.creative_url && !imgError ? (
        <a href={linkHref} target="_blank" rel="noopener noreferrer" className="block">
          <div className="relative aspect-[4/3] bg-slate-900 overflow-hidden flex items-center justify-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={ad.creative_url}
              alt=""
              loading="lazy"
              className="max-w-full max-h-full object-contain transition-transform duration-700 group-hover:scale-[1.03]"
              onError={() => setImgError(true)}
            />
            <div className="absolute inset-x-0 top-0 h-16 bg-gradient-to-b from-black/40 to-transparent pointer-events-none" />
            <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/60 to-transparent pointer-events-none" />
            {/* Status dot */}
            <div className="absolute top-3 right-3">
              <span className={`relative flex h-2.5 w-2.5 rounded-full ${ad.is_active ? "bg-emerald-400" : "bg-gray-400"}`}>
                {ad.is_active && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />}
              </span>
            </div>
            {/* Tags */}
            <div className="absolute top-3 left-3 flex items-center gap-1.5">
              {/* Source platform (Meta / TikTok) */}
              {(() => {
                const src = getSourcePlatform(ad);
                return (
                  <span className={`flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-full sm:backdrop-blur-md bg-white/95 sm:bg-white/90 ${src.color} shadow-sm`}>
                    {src.icon}
                    {src.label}
                  </span>
                );
              })()}
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full sm:backdrop-blur-md bg-black/30 sm:bg-white/20 text-white">
                {FORMAT_LABELS[ad.display_format || ""]?.label || ad.display_format || ad.platform}
              </span>
              {ad.contains_ai_content && (
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-full sm:backdrop-blur-md bg-violet-600/50 sm:bg-violet-500/30 text-white flex items-center gap-1">
                  <Sparkles className="h-2.5 w-2.5" />IA
                </span>
              )}
            </div>
            {/* Advertiser badge with logo */}
            <div className="absolute bottom-3 left-3 flex items-center gap-2">
              {advertiserLogo && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={advertiserLogo} alt="" className="h-7 w-7 rounded-full object-cover border-2 border-white/60 shadow-sm" />
              )}
              <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full sm:backdrop-blur-md bg-black/60 sm:bg-black/40 text-white">
                {ad.competitor_name}
                {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
              </span>
            </div>
            {/* Platform icons */}
            {getPublisherPlatforms(ad).length > 0 && (
              <div className="absolute bottom-3 right-3 flex items-center gap-1">
                {getPublisherPlatforms(ad).map(p => (
                  <span key={p} className="h-6 w-6 rounded-full sm:backdrop-blur-md bg-white/50 sm:bg-white/30 flex items-center justify-center text-white">
                    <PlatformIcon name={p} className="h-3 w-3" />
                  </span>
                ))}
              </div>
            )}
          </div>
        </a>
      ) : (
        <div className="aspect-[4/3] bg-gradient-to-br from-muted to-muted/30 flex flex-col items-center justify-center gap-2 relative">
          {imgError || ad.creative_url?.includes("tiktokcdn") ? (
            <div className="flex flex-col items-center gap-1 text-muted-foreground/30">
              <Play className="h-8 w-8" />
              <span className="text-[9px] uppercase tracking-wider font-medium">Vidéo</span>
            </div>
          ) : <Eye className="h-8 w-8 text-muted-foreground/20" />}
          <div className="flex items-center gap-2">
            {advertiserLogo && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={advertiserLogo} alt="" className="h-6 w-6 rounded-full object-cover" />
            )}
            <span className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-muted text-muted-foreground">
              {ad.competitor_name}
              {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
            </span>
          </div>
          {/* Source platform badge */}
          <div className="absolute top-3 left-3">
            {(() => {
              const src = getSourcePlatform(ad);
              return (
                <span className={`flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-full border ${src.bg} ${src.color}`}>
                  {src.icon}
                  {src.label}
                </span>
              );
            })()}
          </div>
        </div>
      )}

      {/* Content */}
      <div className="p-4 space-y-2.5">
        {ad.title && <p className="text-sm font-semibold leading-snug line-clamp-2">{ad.title}</p>}
        {ad.ad_text && <p className="text-[13px] leading-relaxed line-clamp-2 text-foreground/70">{ad.ad_text}</p>}

        {/* Quick metrics strip (always visible) */}
        <div className="flex items-center gap-2 flex-wrap">
          {ad.ad_type && (
            <span className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
              ad.ad_type === "branding" ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
              ad.ad_type === "performance" ? "bg-orange-50 text-orange-700 border-orange-200" :
              ad.ad_type === "dts" ? "bg-blue-50 text-blue-700 border-blue-200" :
              "bg-gray-50 text-gray-700 border-gray-200"
            }`}>
              {ad.ad_type === "branding" && <Megaphone className="h-2.5 w-2.5" />}
              {ad.ad_type === "performance" && <TrendingUp className="h-2.5 w-2.5" />}
              {ad.ad_type === "dts" && <MapPin className="h-2.5 w-2.5" />}
              {ad.ad_type === "branding" ? "Branding" : ad.ad_type === "performance" ? "Performance" : ad.ad_type === "dts" ? "Drive-to-Store" : ad.ad_type}
            </span>
          )}
          {ad.eu_total_reach != null && ad.eu_total_reach > 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100">
              <Target className="h-2.5 w-2.5" />{formatNumber(ad.eu_total_reach)}
            </span>
          )}
          {durationDays > 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
              <Calendar className="h-2.5 w-2.5" />{durationDays}j
            </span>
          )}
          {ad.cta && (
            <span className="inline-block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
              {ad.cta}
            </span>
          )}
          {ad.link_url && (
            <a href={ad.link_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-[10px] text-blue-600 hover:text-blue-700 transition-colors truncate max-w-[140px]">
              <Link2 className="h-2.5 w-2.5 shrink-0" />
              {(() => { try { return new URL(ad.link_url!).hostname.replace("www.", ""); } catch { return ad.link_url; } })()}
            </a>
          )}
          {/* Budget estimation from CPM benchmarks */}
          {(() => {
            const budget = estimateBudget(ad);
            if (!budget) return null;
            return (
              <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100" title="Estimation basée sur le CPM benchmark du pays">
                <TrendingUp className="h-2.5 w-2.5" />~{formatNumber(budget.min)}-{formatNumber(budget.max)}€
              </span>
            );
          })()}
        </div>

        {/* Creative Analysis badges */}
        {ad.creative_analyzed_at && ad.creative_score != null && ad.creative_score > 0 && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                ad.creative_score >= 80 ? "bg-emerald-50 text-emerald-700 border-emerald-200" :
                ad.creative_score >= 60 ? "bg-blue-50 text-blue-700 border-blue-200" :
                ad.creative_score >= 40 ? "bg-amber-50 text-amber-700 border-amber-200" :
                "bg-red-50 text-red-700 border-red-200"
              }`}>
                <Sparkles className="h-2.5 w-2.5" />{ad.creative_score}
              </span>
              {ad.creative_concept && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 text-[10px] font-medium border border-violet-200">
                  <Brain className="h-2.5 w-2.5" />{ad.creative_concept}
                </span>
              )}
              {ad.creative_tone && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-pink-50 text-pink-700 text-[10px] font-medium border border-pink-200">
                  <Zap className="h-2.5 w-2.5" />{ad.creative_tone}
                </span>
              )}
              {ad.product_category && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-medium border border-emerald-200">
                  <Tag className="h-2.5 w-2.5" />{ad.product_category}
                </span>
              )}
              {ad.ad_objective && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 text-[10px] font-medium border border-sky-200">
                  <Target className="h-2.5 w-2.5" />{ad.ad_objective}
                </span>
              )}
            </div>
            {ad.creative_dominant_colors && ad.creative_dominant_colors.length > 0 && (
              <div className="flex items-center gap-1">
                <Palette className="h-3 w-3 text-muted-foreground/50" />
                {ad.creative_dominant_colors.map((color, i) => (
                  <div key={i} className="h-3.5 w-3.5 rounded border border-gray-200" style={{ backgroundColor: color }} title={color} />
                ))}
                {ad.creative_tags && ad.creative_tags.length > 0 && (
                  <div className="flex items-center gap-1 ml-1">
                    {ad.creative_tags.slice(0, 4).map((tag, i) => (
                      <span key={i} className="px-1.5 py-0 rounded bg-muted text-[9px] text-muted-foreground">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
            {ad.creative_hook && (
              <p className="text-[11px] text-muted-foreground italic leading-snug line-clamp-1">
                {ad.creative_hook}
              </p>
            )}
          </div>
        )}

        {/* Expand toggle */}
        <button onClick={onToggle} className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors w-full">
          {expanded ? <><ChevronUp className="h-3 w-3" />Moins</> : <><ChevronDown className="h-3 w-3" />Details</>}
        </button>

        {/* Expanded */}
        {expanded && (
          <div className="space-y-3 pt-2 border-t border-border/50">
            {/* Payer & Advertiser */}
            {ad.page_name && (
              <div className="flex items-start gap-3 p-3 rounded-xl bg-muted/50">
                <AdvertiserAvatar ad={ad} size="lg" logoUrl={advertiserLogo} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold truncate">{ad.page_name}</span>
                    {ad.page_profile_uri && (
                      <a href={ad.page_profile_uri} target="_blank" rel="noopener noreferrer" className="text-muted-foreground hover:text-foreground shrink-0">
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
                      Payeur
                    </span>
                    {ad.page_like_count != null && ad.page_like_count > 0 && (
                      <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                        <ThumbsUp className="h-3 w-3" />{formatNumber(ad.page_like_count)} likes
                      </span>
                    )}
                    {ad.page_categories && ad.page_categories.length > 0 && (
                      <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                        <Tag className="h-3 w-3" />{ad.page_categories.join(", ")}
                      </span>
                    )}
                  </div>
                  {(ad.payer || ad.beneficiary || ad.byline || ad.disclaimer_label) && (
                    <div className="mt-1.5 space-y-1">
                      {ad.payer && (
                        <div className="flex items-center gap-1.5 text-[11px] text-emerald-700">
                          <span className="font-medium">Payeur :</span>
                          <span className="font-semibold">{ad.payer}</span>
                        </div>
                      )}
                      {ad.beneficiary && (
                        <div className="flex items-center gap-1.5 text-[11px] text-emerald-700">
                          <span className="font-medium">Bénéficiaire :</span>
                          <span className="font-semibold">{ad.beneficiary}</span>
                        </div>
                      )}
                      {!ad.payer && !ad.beneficiary && (ad.byline || ad.disclaimer_label) && (
                        <div className="flex items-center gap-1.5 text-[11px] text-emerald-700">
                          <span className="font-medium">Financeur déclaré :</span>
                          <span className="font-semibold">{ad.byline || ad.disclaimer_label}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Diffusion / Audience */}
            <div className="p-3 rounded-xl bg-blue-50/50 border border-blue-100 space-y-2.5">
              <div className="text-[10px] uppercase tracking-widest text-blue-600 font-semibold">Diffusion & Audience</div>

              {/* EU Transparency: Age, Gender, Location, Reach */}
              {(ad.age_min != null || ad.eu_total_reach != null) && (
                <div className="grid grid-cols-2 gap-2">
                  {ad.age_min != null && (
                    <div className="p-2 rounded-lg bg-white/70">
                      <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-0.5">
                        <UserCheck className="h-3 w-3" />Age
                      </div>
                      <div className="text-sm font-bold tabular-nums">{ad.age_min}-{ad.age_max}+ ans</div>
                    </div>
                  )}
                  {ad.gender_audience && (
                    <div className="p-2 rounded-lg bg-white/70">
                      <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-0.5">
                        <Users className="h-3 w-3" />Genre
                      </div>
                      <div className="text-sm font-bold">
                        {genderLabel(ad.gender_audience)}
                      </div>
                    </div>
                  )}
                  {ad.eu_total_reach != null && ad.eu_total_reach > 0 && (
                    <div className="p-2 rounded-lg bg-white/70">
                      <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-0.5">
                        <Target className="h-3 w-3" />Couverture EU
                      </div>
                      <div className="text-sm font-bold tabular-nums">{formatNumber(ad.eu_total_reach)}</div>
                    </div>
                  )}
                  {ad.location_audience && ad.location_audience.length > 0 && (
                    <div className="p-2 rounded-lg bg-white/70">
                      <div className="flex items-center gap-1 text-[10px] text-muted-foreground mb-0.5">
                        <MapPin className="h-3 w-3" />Lieu
                      </div>
                      <div className="text-xs font-medium leading-snug">
                        {ad.location_audience.map(l => l.name).join(", ")}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Age/Gender breakdown mini chart */}
              {ad.age_country_gender_reach && ad.age_country_gender_reach.length > 0 && (
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1.5">Repartition age / genre</div>
                  <div className="space-y-1">
                    {ad.age_country_gender_reach[0].age_gender_breakdowns
                      .filter(b => b.age_range !== "Unknown")
                      .sort((a, b) => AGE_ORDER.indexOf(a.age_range) - AGE_ORDER.indexOf(b.age_range))
                      .map((b) => {
                        const total = b.male + b.female + b.unknown;
                        const maxReach = Math.max(
                          ...ad.age_country_gender_reach![0].age_gender_breakdowns
                            .filter(x => x.age_range !== "Unknown")
                            .map(x => x.male + x.female + x.unknown)
                        );
                        const barPct = maxReach > 0 ? (total / maxReach) * 100 : 0;
                        const malePct = total > 0 ? Math.round((b.male / total) * 100) : 0;
                        const femalePct = total > 0 ? Math.round((b.female / total) * 100) : 0;
                        return (
                          <div key={b.age_range} className="flex items-center gap-2">
                            <span className="text-[10px] tabular-nums text-muted-foreground w-10 text-right shrink-0">{b.age_range}</span>
                            <div className="flex-1 h-3 rounded-full bg-white/50 overflow-hidden flex">
                              <div className="h-full bg-blue-400" style={{ width: `${(b.male / (maxReach || 1)) * 100}%` }} title={`H: ${formatNumber(b.male)} (${malePct}%)`} />
                              <div className="h-full bg-pink-400" style={{ width: `${(b.female / (maxReach || 1)) * 100}%` }} title={`F: ${formatNumber(b.female)} (${femalePct}%)`} />
                            </div>
                            <span className="text-[9px] tabular-nums text-muted-foreground w-12 shrink-0">{formatNumber(total)}</span>
                          </div>
                        );
                      })}
                    <div className="flex items-center gap-3 mt-1 text-[9px] text-muted-foreground">
                      <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-blue-400" />Hommes</span>
                      <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-pink-400" />Femmes</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Platforms */}
              {getPublisherPlatforms(ad).length > 0 && (
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">Plateformes de diffusion</div>
                  <div className="flex flex-wrap gap-1">
                    {getPublisherPlatforms(ad).map((p) => <PlatformPill key={p} name={p} />)}
                  </div>
                </div>
              )}
              {/* Location from targeted_countries (if available) */}
              {ad.targeted_countries && ad.targeted_countries.length > 0 && (
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">Pays cibles</div>
                  <div className="flex flex-wrap gap-1">
                    {ad.targeted_countries.map((c) => (
                      <span key={c} className="inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white border text-foreground/80">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {/* Duration */}
              {ad.start_date && (
                <div>
                  <div className="text-[10px] text-muted-foreground mb-0.5">Duree de diffusion</div>
                  <div className="text-xs font-medium tabular-nums">
                    {formatDate(ad.start_date)}
                    {ad.end_date ? ` \u2192 ${formatDate(ad.end_date)}` : " \u2192 En cours"}
                    {ad.start_date && (
                      <span className="ml-2 text-[10px] text-muted-foreground font-normal">
                        ({(() => {
                          const start = new Date(ad.start_date!);
                          const end = ad.end_date ? new Date(ad.end_date) : new Date();
                          const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
                          return days <= 0 ? "< 1 jour" : days === 1 ? "1 jour" : `${days} jours`;
                        })()})
                      </span>
                    )}
                  </div>
                </div>
              )}
              {/* AI content */}
              {ad.contains_ai_content && (
                <div className="flex items-center gap-1.5 text-[11px] text-violet-600">
                  <Sparkles className="h-3 w-3" />
                  <span className="font-medium">Contenu genere par IA</span>
                </div>
              )}
            </div>

            {/* Description */}
            {ad.link_description && (
              <div className="space-y-1">
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">Description</div>
                <p className="text-xs text-foreground/70 leading-relaxed line-clamp-6">{ad.link_description}</p>
              </div>
            )}

            {/* Spend & impressions */}
            {((ad.estimated_spend_min && ad.estimated_spend_min > 0) || (ad.impressions_min && ad.impressions_min > 0)) && (
              <div className="grid grid-cols-2 gap-2">
                {ad.estimated_spend_min != null && ad.estimated_spend_min > 0 && (
                  <div className="p-2 rounded-lg bg-emerald-50/50">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Budget</div>
                    <div className="text-sm font-bold mt-0.5 tabular-nums">
                      {formatNumber(ad.estimated_spend_min)}&ndash;{formatNumber(ad.estimated_spend_max || 0)} &euro;
                    </div>
                  </div>
                )}
                {ad.impressions_min != null && ad.impressions_min > 0 && (
                  <div className="p-2 rounded-lg bg-blue-50/50">
                    <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Impressions</div>
                    <div className="text-sm font-bold mt-0.5 tabular-nums">
                      {formatNumber(ad.impressions_min)}&ndash;{formatNumber(ad.impressions_max || 0)}
                    </div>
                  </div>
                )}
              </div>
            )}
            {/* CPM-based budget estimation */}
            {(() => {
              const budget = estimateBudget(ad);
              if (!budget) return null;
              const country = ad.targeted_countries?.[0] || "FR";
              const source = normalizeSource(ad.platform);
              const cpm = ((CPM_BENCHMARKS[country] || CPM_BENCHMARKS.DEFAULT) as Record<string, number>)[source] || CPM_BENCHMARKS.DEFAULT.meta;
              const sourceLabel = SOURCE_CONFIG[source]?.label || "Meta";
              return (
                <div className="p-3 rounded-lg bg-gradient-to-r from-emerald-50/80 to-teal-50/80 border border-emerald-100">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-1 text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">Budget estim&eacute; (CPM) <InfoTooltip text={METHODOLOGY.budget} /></div>
                    <span className="text-[9px] text-emerald-600 bg-emerald-100 px-1.5 py-0.5 rounded-full">Benchmark {country}</span>
                  </div>
                  <div className="text-lg font-bold text-emerald-700 tabular-nums">
                    {formatNumber(budget.min)} - {formatNumber(budget.max)} €
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-1">
                    CPM {sourceLabel} : ~{cpm}€ &middot; Reach : {formatNumber(ad.eu_total_reach || 0)}
                  </div>
                </div>
              );
            })()}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-border/50">
          {ad.start_date && (
            <span className="text-[11px] text-muted-foreground tabular-nums">
              {formatDate(ad.start_date)}
              {ad.end_date && ` \u2192 ${formatDate(ad.end_date)}`}
            </span>
          )}
          <a
            href={ad.ad_library_url || (ad.platform === "google" ? `https://adstransparency.google.com/advertiser/${ad.ad_id}` : `https://www.facebook.com/ads/library/?id=${ad.ad_id}`)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-blue-600 hover:text-blue-700 transition-colors flex items-center gap-1"
          >
            <ArrowUpRight className="h-3 w-3" />{ad.platform === "google" ? "Google Transparency" : "Ad Library"}
          </a>
        </div>
      </div>
    </div>
  );
}

/* ─────────────── Demographics Panel ─────────────── */

function DemographicsPanel({ filteredAds }: { filteredAds: AdWithCompetitor[] }) {
  const [demoCountry, setDemoCountry] = useState<string>("all");
  const [demoAgeFilter, setDemoAgeFilter] = useState<string>("all");

  // Collect all available countries from age_country_gender_reach
  const availableCountries = useMemo(() => {
    const set = new Set<string>();
    filteredAds.forEach(a => {
      (a.age_country_gender_reach || []).forEach(c => set.add(c.country));
    });
    return Array.from(set).sort();
  }, [filteredAds]);

  // Aggregate demographics across all filtered ads
  const demographics = useMemo(() => {
    let totalMale = 0, totalFemale = 0, totalUnknown = 0;
    const ageRanges: Record<string, { male: number; female: number; unknown: number }> = {};
    let adsWithData = 0;
    let totalReach = 0;

    filteredAds.forEach(a => {
      if (!a.age_country_gender_reach || a.age_country_gender_reach.length === 0) return;
      adsWithData++;
      if (a.eu_total_reach) totalReach += a.eu_total_reach;

      a.age_country_gender_reach.forEach(countryData => {
        if (demoCountry !== "all" && countryData.country !== demoCountry) return;

        countryData.age_gender_breakdowns
          .filter(b => b.age_range !== "Unknown")
          .forEach(b => {
            const m = b.male || 0, f = b.female || 0, u = b.unknown || 0;
            // Apply age filter for gender stats
            if (demoAgeFilter !== "all" && b.age_range !== demoAgeFilter) {
              // Still count in age distribution but not in gender totals
            } else {
              totalMale += m;
              totalFemale += f;
              totalUnknown += u;
            }

            // Always aggregate age ranges (for age distribution chart)
            if (!ageRanges[b.age_range]) ageRanges[b.age_range] = { male: 0, female: 0, unknown: 0 };
            ageRanges[b.age_range].male += m;
            ageRanges[b.age_range].female += f;
            ageRanges[b.age_range].unknown += u;
          });
      });
    });

    const genderTotal = totalMale + totalFemale + totalUnknown;
    const malePct = genderTotal > 0 ? Math.round((totalMale / genderTotal) * 100) : 0;
    const femalePct = genderTotal > 0 ? Math.round((totalFemale / genderTotal) * 100) : 0;
    const unknownPct = genderTotal > 0 ? 100 - malePct - femalePct : 0;

    // Sort age ranges
    const sortedAges = AGE_ORDER
      .filter(age => ageRanges[age])
      .map(age => ({
        range: age,
        ...ageRanges[age],
        total: ageRanges[age].male + ageRanges[age].female + ageRanges[age].unknown,
      }));

    const maxAgeTotal = Math.max(...sortedAges.map(a => a.total), 1);

    return {
      totalMale, totalFemale, totalUnknown, genderTotal,
      malePct, femalePct, unknownPct,
      sortedAges, maxAgeTotal,
      adsWithData, totalReach,
    };
  }, [filteredAds, demoCountry, demoAgeFilter]);

  if (demographics.adsWithData === 0) return null;

  return (
    <div className="rounded-2xl border bg-card overflow-hidden">
      <div className="px-5 py-4 border-b bg-gradient-to-r from-violet-50/50 to-pink-50/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-pink-500 shadow-md shadow-violet-200/30">
              <PieChart className="h-4 w-4 text-white" />
            </div>
            <div>
              <h3 className="text-[14px] font-semibold text-foreground flex items-center gap-1.5">Audience & D&eacute;mographiques <InfoTooltip text={METHODOLOGY.demographics} /></h3>
              <p className="text-[11px] text-muted-foreground">{demographics.adsWithData} pubs avec donn&eacute;es de transparence EU</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold tabular-nums">{formatNumber(demographics.totalReach)}</div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Couverture EU totale</div>
          </div>
        </div>

        {/* Sub-filters row */}
        <div className="flex items-center gap-3 mt-3 flex-wrap">
          <div className="flex items-center gap-1.5">
            <Globe className="h-3 w-3 text-muted-foreground" />
            <select
              value={demoCountry}
              onChange={(e) => setDemoCountry(e.target.value)}
              className="text-xs bg-white border rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            >
              <option value="all">Tous les pays</option>
              {availableCountries.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <UserCheck className="h-3 w-3 text-muted-foreground" />
            <select
              value={demoAgeFilter}
              onChange={(e) => setDemoAgeFilter(e.target.value)}
              className="text-xs bg-white border rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            >
              <option value="all">Toutes les tranches</option>
              {AGE_ORDER.map(age => <option key={age} value={age}>{age} ans</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className="p-5 grid gap-6 lg:grid-cols-2">
        {/* Gender Distribution */}
        <div className="space-y-3">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Repartition par genre
            {demoAgeFilter !== "all" && <span className="text-violet-600 ml-1">({demoAgeFilter} ans)</span>}
          </div>

          {/* Big donut-style display */}
          <div className="flex items-center gap-6">
            {/* Male */}
            <div className="flex-1 text-center">
              <div className="relative inline-flex items-center justify-center">
                <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" strokeWidth="3" className="text-muted/30" />
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" strokeWidth="3" className="text-blue-500"
                    strokeDasharray={`${demographics.malePct} ${100 - demographics.malePct}`} strokeLinecap="round" />
                </svg>
                <span className="absolute text-lg font-bold text-blue-600 tabular-nums">{demographics.malePct}%</span>
              </div>
              <div className="mt-1.5 text-xs font-semibold text-blue-600">Hommes</div>
              <div className="text-[10px] text-muted-foreground tabular-nums">{formatNumber(demographics.totalMale)}</div>
            </div>

            {/* Female */}
            <div className="flex-1 text-center">
              <div className="relative inline-flex items-center justify-center">
                <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90">
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" strokeWidth="3" className="text-muted/30" />
                  <circle cx="18" cy="18" r="15.9" fill="none" stroke="currentColor" strokeWidth="3" className="text-pink-500"
                    strokeDasharray={`${demographics.femalePct} ${100 - demographics.femalePct}`} strokeLinecap="round" />
                </svg>
                <span className="absolute text-lg font-bold text-pink-600 tabular-nums">{demographics.femalePct}%</span>
              </div>
              <div className="mt-1.5 text-xs font-semibold text-pink-600">Femmes</div>
              <div className="text-[10px] text-muted-foreground tabular-nums">{formatNumber(demographics.totalFemale)}</div>
            </div>

            {demographics.unknownPct > 1 && (
              <div className="text-center">
                <div className="text-sm font-bold text-gray-400 tabular-nums">{demographics.unknownPct}%</div>
                <div className="text-[10px] text-muted-foreground">Inconnu</div>
              </div>
            )}
          </div>

          {/* Combined bar */}
          <GenderBar male={demographics.totalMale} female={demographics.totalFemale} unknown={demographics.totalUnknown} />
        </div>

        {/* Age Distribution */}
        <div className="space-y-3">
          <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Repartition par tranche d&apos;age
          </div>

          <div className="space-y-2">
            {demographics.sortedAges.map((age) => {
              const pct = demographics.maxAgeTotal > 0 ? Math.round((age.total / demographics.maxAgeTotal) * 100) : 0;
              const totalAll = demographics.sortedAges.reduce((s, a) => s + a.total, 0);
              const pctOfTotal = totalAll > 0 ? Math.round((age.total / totalAll) * 100) : 0;
              const malePct = age.total > 0 ? Math.round((age.male / age.total) * 100) : 0;
              const femalePct = age.total > 0 ? Math.round((age.female / age.total) * 100) : 0;
              return (
                <div key={age.range} className="group/age relative">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] tabular-nums text-muted-foreground w-10 text-right shrink-0 font-medium">{age.range}</span>
                    <div className="flex-1 h-5 rounded-lg bg-muted/50 overflow-hidden flex relative cursor-default">
                      <div className="h-full bg-blue-400/90 transition-all" style={{ width: `${(age.male / demographics.maxAgeTotal) * 100}%` }} />
                      <div className="h-full bg-pink-400/90 transition-all" style={{ width: `${(age.female / demographics.maxAgeTotal) * 100}%` }} />
                      {/* Percentage label inside bar */}
                      <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-white mix-blend-difference tabular-nums">
                        {pctOfTotal}%
                      </span>
                    </div>
                    <span className="text-[10px] tabular-nums text-muted-foreground w-16 text-right shrink-0">
                      {formatNumber(age.total)}
                    </span>
                  </div>
                  {/* Hover tooltip - positioned absolutely so no layout shift */}
                  <div className="pointer-events-none opacity-0 group-hover/age:opacity-100 transition-opacity absolute left-12 -top-7 z-10 flex items-center gap-2 px-2.5 py-1 rounded-lg bg-popover border shadow-lg text-[9px]">
                    <span className="text-blue-600 font-semibold">{malePct}% H</span>
                    <span className="text-pink-600 font-semibold">{femalePct}% F</span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center gap-3 text-[9px] text-muted-foreground pt-1">
            <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-blue-400" />Hommes</span>
            <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-sm bg-pink-400" />Femmes</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────── Insights & Intelligence ─────────────── */

function InsightsSection({ filteredAds, stats }: { filteredAds: AdWithCompetitor[]; stats: any }) {
  const insights = useMemo(() => {
    const result: { icon: React.ReactNode; title: string; text: string; severity: string; action?: string }[] = [];
    if (filteredAds.length === 0) return result;

    const reachByComp = new Map<string, number>();
    const spendByComp = new Map<string, { min: number; max: number; count: number }>();
    const durationByComp = new Map<string, { total: number; count: number }>();
    const formatsByComp = new Map<string, Set<string>>();
    const platformsByComp = new Map<string, Set<string>>();
    let totalMetaAds = 0, totalGoogleAds = 0, totalTikTokAds = 0;

    filteredAds.forEach(a => {
      if (a.eu_total_reach) reachByComp.set(a.competitor_name, (reachByComp.get(a.competitor_name) || 0) + a.eu_total_reach);
      const src = a.platform === "tiktok" ? "tiktok" : a.platform === "google" ? "google" : "meta";
      if (src === "meta") totalMetaAds++;
      else if (src === "google") totalGoogleAds++;
      else totalTikTokAds++;
      const budget = estimateBudget(a);
      if (budget) {
        const s = spendByComp.get(a.competitor_name) || { min: 0, max: 0, count: 0 };
        s.min += budget.min; s.max += budget.max; s.count++;
        spendByComp.set(a.competitor_name, s);
      }
      if (a.start_date && a.end_date) {
        const days = Math.ceil((new Date(a.end_date).getTime() - new Date(a.start_date).getTime()) / 86400000);
        if (days > 0) {
          const d = durationByComp.get(a.competitor_name) || { total: 0, count: 0 };
          d.total += days; d.count++;
          durationByComp.set(a.competitor_name, d);
        }
      }
      if (a.display_format) {
        if (!formatsByComp.has(a.competitor_name)) formatsByComp.set(a.competitor_name, new Set());
        formatsByComp.get(a.competitor_name)!.add(a.display_format);
      }
      if (!platformsByComp.has(a.competitor_name)) platformsByComp.set(a.competitor_name, new Set());
      platformsByComp.get(a.competitor_name)!.add(src);
    });

    // 1. Share of Voice & Media Pressure
    const reachSorted = Array.from(reachByComp.entries()).sort((a, b) => b[1] - a[1]);
    const totalReach = reachSorted.reduce((s, [, v]) => s + v, 0);
    if (reachSorted.length >= 2 && totalReach > 0) {
      const leaderPct = Math.round((reachSorted[0][1] / totalReach) * 100);
      const secondPct = Math.round((reachSorted[1][1] / totalReach) * 100);
      result.push({
        icon: <Target className="h-4 w-4" />,
        title: "Share of Voice",
        text: `${reachSorted[0][0]} capte ${leaderPct}% de la couverture EU (${formatNumber(reachSorted[0][1])} reach). ${leaderPct > 50 ? "Position dominante qui laisse peu d'espace aux challengers." : `Ecart serré avec ${reachSorted[1][0]} (${secondPct}%) — le marché est disputé.`}`,
        severity: leaderPct > 50 ? "danger" : "warning",
        action: leaderPct > 50 ? `Augmenter la pression media pour contrer la domination de ${reachSorted[0][0]}` : "Intensifier le reach sur les segments sous-exploités",
      });
    }

    // 2. Media Mix & Channel Strategy
    const total = filteredAds.length;
    const metaPct = Math.round((totalMetaAds / total) * 100);
    const googlePct = Math.round((totalGoogleAds / total) * 100);
    const tiktokPct = Math.round((totalTikTokAds / total) * 100);
    if (total > 10) {
      const dominant = metaPct > googlePct && metaPct > tiktokPct ? "Meta" : googlePct > tiktokPct ? "Google" : "TikTok";
      const dominantPct = Math.max(metaPct, googlePct, tiktokPct);
      result.push({
        icon: <PieChart className="h-4 w-4" />,
        title: "Stratégie Media Mix",
        text: dominantPct > 70
          ? `Le secteur sur-investit en ${dominant} (${dominantPct}%). Les annonceurs qui diversifient leur mix media obtiennent un meilleur ROI incrémental.`
          : tiktokPct < 10
          ? `TikTok ne représente que ${tiktokPct}% des créations — un levier sous-exploité pour toucher les 18-34 ans, qui constituent souvent le coeur de cible en acquisition.`
          : `Mix media équilibré (Meta ${metaPct}%, Google ${googlePct}%, TikTok ${tiktokPct}%). Bonne couverture multi-canal du parcours client.`,
        severity: dominantPct > 70 ? "warning" : tiktokPct < 10 ? "info" : "success",
        action: tiktokPct < 10 ? "Tester des campagnes TikTok Spark Ads pour diversifier l'acquisition" : undefined,
      });
    }

    // 3. Creative Fatigue & Rotation Strategy
    const avgDurations = Array.from(durationByComp.entries())
      .map(([name, d]) => ({ name, avg: Math.round(d.total / d.count) }))
      .sort((a, b) => b.avg - a.avg);
    if (avgDurations.length >= 2) {
      const longest = avgDurations[0], shortest = avgDurations[avgDurations.length - 1];
      const ratio = longest.avg / Math.max(shortest.avg, 1);
      if (longest.avg > 30) {
        result.push({
          icon: <Calendar className="h-4 w-4" />,
          title: "Fatigue Créative",
          text: `${longest.name} maintient ses visuels ${longest.avg}j en moyenne${ratio > 2 ? ` (${Math.round(ratio)}x plus que ${shortest.name})` : ""}. Au-delà de 21 jours, le CTR chute de 20-40% en moyenne. Risque d'ad blindness élevé.`,
          severity: longest.avg > 45 ? "danger" : "warning",
          action: "Mettre en place un calendrier de rotation créative toutes les 2-3 semaines avec des variantes A/B",
        });
      }
    }

    // 4. Creative Diversification
    const fmtDiv = Array.from(formatsByComp.entries())
      .map(([name, fmts]) => ({ name, count: fmts.size, formats: Array.from(fmts) }))
      .sort((a, b) => b.count - a.count);
    if (fmtDiv.length >= 2) {
      const leader = fmtDiv[0], laggard = fmtDiv[fmtDiv.length - 1];
      if (leader.count > laggard.count) {
        const hasVideo = leader.formats.some(f => f.includes("VIDEO"));
        result.push({
          icon: <Palette className="h-4 w-4" />,
          title: "Diversité Créative",
          text: `${leader.name} déploie ${leader.count} formats (${leader.formats.map(f => FORMAT_LABELS[f]?.label || f.toLowerCase()).join(", ")}) vs ${laggard.count} pour ${laggard.name}. ${hasVideo ? "La vidéo, présente dans leur arsenal, génère en moyenne 3x plus d'engagement que le statique." : "L'absence de vidéo est une opportunité manquée — le format le plus engageant."}`,
          severity: "success",
          action: !hasVideo ? "Produire des vidéos courtes (6-15s) adaptées aux feeds mobile" : undefined,
        });
      }
    }

    // 5. Budget Intelligence
    const spendSorted = Array.from(spendByComp.entries())
      .map(([name, s]) => ({ name, avg: Math.round((s.min + s.max) / 2), count: s.count }))
      .sort((a, b) => b.avg - a.avg);
    if (spendSorted.length >= 2 && spendSorted[0].avg > 0) {
      const topSpender = spendSorted[0];
      const efficiency = topSpender.count > 0 ? Math.round(topSpender.avg / topSpender.count) : 0;
      result.push({
        icon: <TrendingUp className="h-4 w-4" />,
        title: "Intelligence Budgétaire",
        text: `${topSpender.name} investit ~${formatNumber(topSpender.avg)}€ estimés sur ${topSpender.count} créations (${formatNumber(efficiency)}€/pub). ${spendSorted.length > 2 ? `Les 3 premiers annonceurs concentrent ${Math.round(spendSorted.slice(0, 3).reduce((s, x) => s + x.avg, 0) / spendSorted.reduce((s, x) => s + x.avg, 0) * 100)}% du budget total estimé.` : ""}`,
        severity: "info",
        action: "Optimiser le ratio budget/créations en testant plus de variantes à moindre coût unitaire",
      });
    }

    // 6. Multi-channel presence analysis
    const multiChannel = Array.from(platformsByComp.entries())
      .map(([name, plats]) => ({ name, channels: plats.size }))
      .sort((a, b) => b.channels - a.channels);
    const monoChannel = multiChannel.filter(c => c.channels === 1);
    if (monoChannel.length > 0 && multiChannel[0].channels >= 2) {
      result.push({
        icon: <Globe className="h-4 w-4" />,
        title: "Présence Omnicanale",
        text: `${monoChannel.map(c => c.name).join(", ")} ${monoChannel.length > 1 ? "ne sont présents que" : "n'est présent que"} sur un seul canal. ${multiChannel[0].name} couvre ${multiChannel[0].channels} canaux, maximisant les points de contact tout au long du funnel.`,
        severity: "warning",
        action: "Déployer une stratégie full-funnel : awareness (Meta/TikTok), consideration (Google Display), conversion (Search)",
      });
    }

    return result;
  }, [filteredAds, stats]);

  if (insights.length === 0) return null;
  const sevStyles: Record<string, { bg: string; iconBg: string; iconColor: string; accent: string; border: string }> = {
    info: { bg: "bg-blue-50/60", iconBg: "bg-blue-100", iconColor: "text-blue-600", accent: "text-blue-700", border: "border-blue-200/60" },
    success: { bg: "bg-emerald-50/60", iconBg: "bg-emerald-100", iconColor: "text-emerald-600", accent: "text-emerald-700", border: "border-emerald-200/60" },
    warning: { bg: "bg-amber-50/60", iconBg: "bg-amber-100", iconColor: "text-amber-600", accent: "text-amber-700", border: "border-amber-200/60" },
    danger: { bg: "bg-red-50/60", iconBg: "bg-red-100", iconColor: "text-red-600", accent: "text-red-700", border: "border-red-200/60" },
  };

  return (
    <div className="rounded-2xl border bg-card overflow-hidden">
      <div className="px-5 py-4 border-b bg-gradient-to-r from-amber-50/50 to-orange-50/50">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-md shadow-amber-200/30">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Diagnostic Expert</h3>
            <p className="text-[11px] text-muted-foreground">Analyse stratégique par notre IA marketing</p>
          </div>
        </div>
      </div>
      <div className="p-5 grid grid-cols-1 lg:grid-cols-2 gap-4">
        {insights.map((ins, i) => {
          const s = sevStyles[ins.severity] || sevStyles.info;
          return (
            <div key={i} className={`rounded-xl border p-4 transition-all hover:shadow-sm ${s.bg} ${s.border}`}>
              <div className="flex items-start gap-3">
                <div className={`flex h-8 w-8 items-center justify-center rounded-lg shrink-0 ${s.iconBg}`}>
                  <div className={s.iconColor}>{ins.icon}</div>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mb-1">{ins.title}</div>
                  <p className="text-[12px] leading-relaxed text-foreground/80">{ins.text}</p>
                  {ins.action && (
                    <div className="mt-2.5 flex items-start gap-1.5 px-2.5 py-2 rounded-lg bg-white/60 border border-white">
                      <Lightbulb className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                      <p className="text-[11px] font-medium text-foreground/70 leading-snug">{ins.action}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CompetitorComparison({ filteredAds, stats, competitors, brandName }: { filteredAds: AdWithCompetitor[]; stats: any; competitors: any[]; brandName?: string }) {
  const data = useMemo(() => {
    const compLogoByName = new Map<string, string>();
    competitors.forEach((c: any) => { if (c.logo_url) compLogoByName.set(c.name.toLowerCase(), c.logo_url); });
    return Array.from((stats.byCompetitor as Map<string, any>).entries())
      .map(([name, d]: [string, any]) => {
        const ads = filteredAds.filter(a => a.competitor_name === name);
        const reach = ads.reduce((s, a) => s + (a.eu_total_reach || 0), 0);
        const fmts = Array.from(new Set(ads.map(a => a.display_format).filter(Boolean)));
        const plats = Array.from(new Set(ads.flatMap(a => getPublisherPlatforms(a)))) as string[];
        const durs = ads.filter(a => a.start_date).map(a => Math.ceil(((a.end_date ? new Date(a.end_date) : new Date()).getTime() - new Date(a.start_date!).getTime()) / 86400000)).filter(x => x > 0);
        const avgDur = durs.length > 0 ? Math.round(durs.reduce((s, x) => s + x, 0) / durs.length) : 0;
        const logo = compLogoByName.get(name.toLowerCase());
        return { name, total: d.total, active: d.active, reach, fmts, plats, avgDur, logo, spendMin: d.spendMin || 0, spendMax: d.spendMax || 0 };
      })
      .sort((a, b) => b.reach - a.reach);
  }, [filteredAds, stats]);

  if (data.length === 0) return null;
  const maxReach = Math.max(...data.map(c => c.reach), 1);

  return (
    <div className="rounded-2xl border bg-card overflow-hidden">
      <div className="px-5 py-4 border-b bg-gradient-to-r from-violet-50/50 to-indigo-50/50">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-md shadow-violet-200/30">
            <BarChart3 className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-[14px] font-semibold text-foreground">Comparatif Concurrentiel</h3>
            <p className="text-[11px] text-muted-foreground">Vue d&apos;ensemble des strat&eacute;gies publicitaires</p>
          </div>
        </div>
      </div>
      <div className="divide-y">
        {data.map((c, i) => {
          const isBrand = !!(brandName && c.name.toLowerCase() === brandName.toLowerCase());
          return (
          <div key={c.name} className={`px-4 sm:px-5 py-4 hover:bg-muted/20 transition-colors ${isBrand ? "bg-violet-50/50 ring-1 ring-violet-200" : ""}`}>
            <div className="flex items-center gap-3 sm:gap-4">
              <div className={`h-7 w-7 sm:h-8 sm:w-8 rounded-full flex items-center justify-center text-xs sm:text-sm font-bold shrink-0 ${i === 0 ? "bg-amber-100 text-amber-700" : i === 1 ? "bg-slate-100 text-slate-600" : "bg-orange-50 text-orange-600"}`}>
                {i + 1}
              </div>
              <div className="flex items-center gap-2 min-w-0 flex-1 sm:flex-none sm:w-36 shrink-0">
                {c.logo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.logo} alt="" className="h-7 w-7 sm:h-8 sm:w-8 rounded-full object-cover border border-border shrink-0" />
                ) : (
                  <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center shrink-0">
                    <span className="text-[9px] sm:text-[10px] font-bold text-slate-600">{c.name.slice(0, 2).toUpperCase()}</span>
                  </div>
                )}
                <span className="text-xs sm:text-sm font-semibold truncate">{c.name}</span>
                {isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
              </div>
              {/* Desktop: inline stats */}
              <div className="hidden md:grid flex-1 grid-cols-5 gap-4">
                <div className="text-center">
                  <div className="text-lg font-bold tabular-nums">{c.total}</div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-widest">pubs</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold tabular-nums text-emerald-600">{c.spendMax > 0 ? `${formatNumber(c.spendMin)}-${formatNumber(c.spendMax)}€` : "—"}</div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-widest">budget</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold tabular-nums text-blue-600">{formatNumber(c.reach)}</div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-widest">reach EU</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold tabular-nums">{c.avgDur}<span className="text-xs font-normal text-muted-foreground">j</span></div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-widest">duree moy</div>
                </div>
                <div className="text-center">
                  <div className="flex items-center justify-center gap-1">
                    {c.plats.slice(0, 4).map(p => (
                      <span key={p} className="h-5 w-5 rounded-full bg-muted flex items-center justify-center">
                        <PlatformIcon name={p} className="h-2.5 w-2.5" />
                      </span>
                    ))}
                  </div>
                  <div className="text-[9px] text-muted-foreground uppercase tracking-widest mt-0.5">plateformes</div>
                </div>
              </div>
              {/* Mobile: compact stats */}
              <div className="md:hidden text-right shrink-0">
                <div className="text-base font-bold tabular-nums">{c.total}</div>
                <div className="text-[9px] text-muted-foreground">pubs</div>
              </div>
            </div>
            {/* Mobile: expanded stats row */}
            <div className="md:hidden grid grid-cols-4 gap-2 mt-2.5 ml-10">
              <div>
                <div className="text-xs font-bold tabular-nums text-emerald-600">{c.spendMax > 0 ? `${formatNumber(c.spendMax)}€` : "—"}</div>
                <div className="text-[8px] text-muted-foreground uppercase">budget</div>
              </div>
              <div>
                <div className="text-xs font-bold tabular-nums text-blue-600">{formatNumber(c.reach)}</div>
                <div className="text-[8px] text-muted-foreground uppercase">reach</div>
              </div>
              <div>
                <div className="text-xs font-bold tabular-nums">{c.avgDur}j</div>
                <div className="text-[8px] text-muted-foreground uppercase">duree</div>
              </div>
              <div className="flex items-center gap-0.5">
                {c.plats.slice(0, 4).map(p => (
                  <span key={p} className="h-4 w-4 rounded-full bg-muted flex items-center justify-center">
                    <PlatformIcon name={p} className="h-2 w-2" />
                  </span>
                ))}
              </div>
            </div>
            <div className="ml-10 sm:ml-12 mt-2">
              <div className="h-1.5 rounded-full bg-muted/50 overflow-hidden">
                <div className={`h-full rounded-full ${i === 0 ? "bg-gradient-to-r from-blue-500 to-blue-600" : "bg-blue-300"}`} style={{ width: `${(c.reach / maxReach) * 100}%` }} />
              </div>
              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                {c.fmts.map(f => (
                  <span key={f} className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground">{FORMAT_LABELS[f as string]?.label || f}</span>
                ))}
              </div>
            </div>
          </div>
          ); })}
      </div>
    </div>
  );
}

function MobsuccessRecommendations({ filteredAds, brandName }: { filteredAds: AdWithCompetitor[]; brandName: string }) {
  const recs = useMemo(() => {
    const r: { bu: string; grad: string; title: string; text: string; icon: React.ReactNode }[] = [];
    const hasLocal = filteredAds.some(a => a.location_audience && a.location_audience.some(l => l.type !== "country"));
    if (hasLocal) {
      r.push({ bu: "WIDELY", grad: "from-teal-500 to-emerald-500", title: "Activez le marketing multilocal", text: "Vos concurrents utilisent du ciblage local granulaire. WIDELY transforme vos campagnes nationales en strategies multilocales avec DMP proprietaire et drive-to-store.", icon: <MapPin className="h-4 w-4" /> });
    }
    const brandFmts = new Set(filteredAds.filter(a => brandName && a.competitor_name === brandName).map(a => a.display_format).filter(Boolean));
    const allFmts = new Set(filteredAds.map(a => a.display_format).filter(Boolean));
    if (brandFmts.size < allFmts.size) {
      const missing = Array.from(allFmts).filter(f => !brandFmts.has(f)).map(f => FORMAT_LABELS[f as string]?.label || f);
      r.push({ bu: "STORY", grad: "from-pink-500 to-rose-500", title: "Diversifiez vos creatives", text: `Formats inexploites : ${missing.join(", ")}. STORY produit du contenu social, video et carrousel haute performance.`, icon: <Play className="h-4 w-4" /> });
    }
    const brandReach = filteredAds.filter(a => brandName && a.competitor_name === brandName).reduce((s, a) => s + (a.eu_total_reach || 0), 0);
    const totalReach = filteredAds.reduce((s, a) => s + (a.eu_total_reach || 0), 0);
    const pct = totalReach > 0 ? Math.round((brandReach / totalReach) * 100) : 0;
    r.push({ bu: "SPARKLY", grad: "from-violet-500 to-purple-500", title: "Boostez vos performances digitales", text: `Votre couverture EU represente ${pct}% du marche. SPARKLY optimise vos budgets avec l'IA pour maximiser couverture et ROAS.`, icon: <Zap className="h-4 w-4" /> });
    r.push({ bu: "FARLY", grad: "from-blue-500 to-cyan-500", title: "Accelerez l'acquisition mobile", text: "Completez votre strategie media avec l'acquisition mobile. FARLY combine ASO, Sensego AI et UA pour maximiser installations et retention.", icon: <GooglePlayIcon className="h-4 w-4" /> });
    return r;
  }, [filteredAds]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2.5">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center">
          <Shield className="h-4 w-4 text-white" />
        </div>
        <div>
          <h3 className="text-sm font-semibold">Solutions Mobsuccess</h3>
          <p className="text-[10px] text-muted-foreground">Recommandations basees sur l&apos;analyse concurrentielle</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {recs.map(rec => (
          <div key={rec.bu} className="group rounded-2xl border bg-card p-4 hover:shadow-lg transition-all hover:-translate-y-0.5">
            <div className="flex items-start gap-3">
              <div className={`h-10 w-10 rounded-xl bg-gradient-to-br ${rec.grad} flex items-center justify-center shrink-0 text-white shadow-sm`}>
                {rec.icon}
              </div>
              <div className="min-w-0 flex-1">
                <span className={`text-[9px] font-extrabold uppercase tracking-widest px-2 py-0.5 rounded-full bg-gradient-to-r ${rec.grad} text-white`}>
                  {rec.bu}
                </span>
                <h4 className="text-sm font-semibold leading-snug mt-1">{rec.title}</h4>
                <p className="text-[11px] text-muted-foreground leading-relaxed mt-1">{rec.text}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────────── Page ─────────────── */

export default function AdsPage() {
  const [allAds, setAllAds] = useState<AdWithCompetitor[]>([]);
  const [competitors, setCompetitors] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [expandedAds, setExpandedAds] = useState<Set<string>>(new Set());
  const [visibleCount, setVisibleCount] = useState(12);

  // Filters
  const [filterCompetitors, setFilterCompetitors] = useState<Set<string>>(new Set());
  const [filterPlatforms, setFilterPlatforms] = useState<Set<string>>(new Set());
  const [filterFormats, setFilterFormats] = useState<Set<string>>(new Set());
  const [filterAdvertisers, setFilterAdvertisers] = useState<Set<string>>(new Set());
  const [filterSource, setFilterSource] = useState<Set<string>>(new Set());
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "inactive">("all");
  const [filterDateFrom, setFilterDateFrom] = useState(() => {
    const d = new Date(); d.setDate(d.getDate() - 90);
    return d.toISOString().split("T")[0];
  });
  const [filterDateTo, setFilterDateTo] = useState(() => new Date().toISOString().split("T")[0]);
  const [periodDays, setPeriodDays] = useState<PeriodDays>(90);
  const [searchQuery, setSearchQuery] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [filterGender, setFilterGender] = useState<"none" | "all" | "male" | "female">("none");
  const [filterAdType, setFilterAdType] = useState<"all" | "branding" | "performance" | "dts">("all");
  const [filterCountry, setFilterCountry] = useState<Set<string>>(new Set());
  const [filterLocations, setFilterLocations] = useState<Set<string>>(new Set());
  const [filterCategories, setFilterCategories] = useState<Set<string>>(new Set());
  const [filterObjectives, setFilterObjectives] = useState<Set<string>>(new Set());
  const [expandedFilterSections, setExpandedFilterSections] = useState<Set<string>>(new Set());
  const [categorySearch, setCategorySearch] = useState("");
  const [showAllPayers, setShowAllPayers] = useState(false);
  const [locationSearch, setLocationSearch] = useState("");
  const [advertiserSearch, setAdvertiserSearch] = useState("");
  const [brandName, setBrandName] = useState<string>("");
  const [creativeInsights, setCreativeInsights] = useState<CreativeInsights | null>(null);
  const [analyzingCreatives, setAnalyzingCreatives] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState<{ analyzed: number; errors: number; remaining: number } | null>(null);
  const autoAnalyzedRef = useRef(false);

  function handlePeriodChange(days: PeriodDays) {
    setPeriodDays(days);
    const to = new Date();
    const from = new Date();
    from.setDate(from.getDate() - days);
    setFilterDateFrom(from.toISOString().split("T")[0]);
    setFilterDateTo(to.toISOString().split("T")[0]);
  }

  function deduplicateAds(ads: (Ad & { competitor_name: string })[]) {
    const seen = new Set<string>();
    return ads.filter(a => {
      if (seen.has(a.ad_id)) return false;
      seen.add(a.ad_id);
      return true;
    });
  }

  // SWR-cached data fetches — survive page navigation
  const { data: swrFbAds } = useAPI<(Ad & { competitor_name: string })[]>("/facebook/ads/all");
  const { data: swrTtAds } = useAPI<(Ad & { competitor_name: string })[]>("/tiktok/ads/all");
  const { data: swrGAds } = useAPI<(Ad & { competitor_name: string })[]>("/google/ads/all");
  const { data: swrComps } = useAPI<any[]>("/competitors/?include_brand=true");
  const { data: swrBrand } = useAPI<any>("/brand/profile");
  const { data: swrInsights } = useAPI<CreativeInsights>("/creative/insights");

  // Merge SWR data into state when available
  useEffect(() => {
    const fb = swrFbAds || [];
    const tt = swrTtAds || [];
    const g = swrGAds || [];
    if (fb.length || tt.length || g.length) {
      setAllAds(deduplicateAds([...fb, ...tt, ...g]));
      setLoading(false);
    }
  }, [swrFbAds, swrTtAds, swrGAds]);

  useEffect(() => {
    if (swrComps) setCompetitors(swrComps);
  }, [swrComps]);

  useEffect(() => {
    if (swrBrand?.company_name) setBrandName(swrBrand.company_name);
  }, [swrBrand]);

  useEffect(() => {
    if (swrInsights) setCreativeInsights(swrInsights);
  }, [swrInsights]);

  // If no ads at all after SWR load, loading is still false (empty state)
  useEffect(() => {
    if (swrFbAds !== undefined && swrTtAds !== undefined && swrGAds !== undefined) {
      setLoading(false);
    }
  }, [swrFbAds, swrTtAds, swrGAds]);

  async function loadAll() {
    setLoading(true);
    try {
      const [fbAdsRes, ttAdsRes, gAdsRes, compRes, brandRes] = await Promise.allSettled([
        facebookAPI.getAllAds(),
        tiktokAPI.getAllAds(),
        googleAdsAPI.getAllAds(),
        competitorsAPI.list({ includeBrand: true }),
        brandAPI.getProfile(),
      ]);
      const fbAds = fbAdsRes.status === "fulfilled" ? fbAdsRes.value : [];
      const ttAds = ttAdsRes.status === "fulfilled" ? ttAdsRes.value : [];
      const gAds = gAdsRes.status === "fulfilled" ? gAdsRes.value : [];
      const ads = deduplicateAds([...fbAds, ...ttAds, ...gAds]);
      const comps = compRes.status === "fulfilled" ? compRes.value : [];
      setAllAds(ads);
      if (compRes.status === "fulfilled") setCompetitors(comps);
      if (brandRes.status === "fulfilled") setBrandName(brandRes.value.company_name);
      try {
        const ci = await creativeAPI.getInsights();
        setCreativeInsights(ci);
      } catch {}
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyzeCreatives() {
    setAnalyzingCreatives(true);
    setAnalyzeResult(null);
    try {
      const result = await creativeAPI.analyzeAll(10);
      setAnalyzeResult(result);
      // Refresh insights
      try { const ci = await creativeAPI.getInsights(); setCreativeInsights(ci); } catch {}
      // Refresh ads to get updated creative fields
      const [fbAds, ttAds, gAds] = await Promise.allSettled([
        facebookAPI.getAllAds(), tiktokAPI.getAllAds(), googleAdsAPI.getAllAds(),
      ]);
      setAllAds(deduplicateAds([
        ...(fbAds.status === "fulfilled" ? fbAds.value : []),
        ...(ttAds.status === "fulfilled" ? ttAds.value : []),
        ...(gAds.status === "fulfilled" ? gAds.value : []),
      ]));
    } catch (err) {
      console.error(err);
    } finally {
      setAnalyzingCreatives(false);
    }
  }

  async function handleFetchAll() {
    setFetching(true);
    try {
      // Resolve Facebook page IDs first
      try { await facebookAPI.resolvePageIds(); } catch {}
      for (const c of competitors) {
        try { await facebookAPI.fetchAds(c.id); } catch {}
        try { await tiktokAPI.fetchAds(c.id); } catch {}
        try { await googleAdsAPI.fetchAds(c.id); } catch {}
      }
      // Enrich with EU transparency data (multiple rounds, 25 ads at a time)
      for (let round = 0; round < 5; round++) {
        try {
          const r = await facebookAPI.enrichTransparency();
          if (r.enriched === 0) break;
        } catch { break; }
      }
      const [fbAds, ttAds, gAds] = await Promise.allSettled([
        facebookAPI.getAllAds(),
        tiktokAPI.getAllAds(),
        googleAdsAPI.getAllAds(),
      ]);
      setAllAds(deduplicateAds([
        ...(fbAds.status === "fulfilled" ? fbAds.value : []),
        ...(ttAds.status === "fulfilled" ? ttAds.value : []),
        ...(gAds.status === "fulfilled" ? gAds.value : []),
      ]));
    } catch (err) {
      console.error(err);
    } finally {
      setFetching(false);
    }
  }

  function toggleFilter(set: Set<string>, value: string, setter: (s: Set<string>) => void) {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    setter(next);
  }

  function clearAllFilters() {
    setFilterCompetitors(new Set());
    setFilterPlatforms(new Set());
    setFilterFormats(new Set());
    setFilterAdvertisers(new Set());
    setFilterStatus("all");
    setFilterDateFrom("");
    setFilterDateTo("");
    setSearchQuery("");
    setFilterGender("none");
    setFilterLocations(new Set());
    setFilterCategories(new Set());
    setFilterObjectives(new Set());
  }

  // Build advertiser logos map: always use competitor logo_url
  const advertiserLogos = useMemo(() => {
    const map = new Map<string, string>();
    const compLogoByName = new Map<string, string>();
    competitors.forEach(c => {
      if (c.logo_url) compLogoByName.set(c.name.toLowerCase(), c.logo_url);
    });
    allAds.forEach(a => {
      if (!a.page_name || map.has(a.page_name)) return;
      const compLogo = compLogoByName.get(a.competitor_name?.toLowerCase() || "");
      if (compLogo) {
        map.set(a.page_name, compLogo);
      }
    });
    return map;
  }, [allAds, competitors]);

  // Derive available filter values from all ads
  const availableCompetitors = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => map.set(a.competitor_name, (map.get(a.competitor_name) || 0) + 1));
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  const availablePlatforms = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => getPublisherPlatforms(a).forEach(p => map.set(p, (map.get(p) || 0) + 1)));
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  const availableFormats = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => { if (a.display_format) map.set(a.display_format, (map.get(a.display_format) || 0) + 1); });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  // Count sources from date-filtered ads (independent of source filter to avoid circular dep)
  const availableSources = useMemo(() => {
    const map = new Map<string, number>();
    let total = 0;
    allAds.forEach(a => {
      if (filterDateFrom && a.start_date && a.start_date < filterDateFrom) return;
      if (filterDateTo && a.start_date && a.start_date > filterDateTo) return;
      const src = normalizeSource(a.platform);
      map.set(src, (map.get(src) || 0) + 1);
      total++;
    });
    return { entries: Array.from(map.entries()).sort((a, b) => b[1] - a[1]), total };
  }, [allAds, filterDateFrom, filterDateTo]);

  const availableAdvertisers = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => {
      const pname = a.page_name || "Inconnu";
      map.set(pname, (map.get(pname) || 0) + 1);
    });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  const availableLocations = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => {
      (a.location_audience || []).forEach(loc => {
        const name = loc.name.split(":")[0].trim();
        map.set(name, (map.get(name) || 0) + 1);
      });
    });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  const availableCategories = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => {
      if (a.product_category) map.set(a.product_category, (map.get(a.product_category) || 0) + 1);
    });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  const availableObjectives = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => {
      if (a.ad_objective) map.set(a.ad_objective, (map.get(a.ad_objective) || 0) + 1);
    });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  const genderCounts = useMemo(() => {
    const counts = { all: 0, male: 0, female: 0 };
    allAds.forEach(a => {
      const g = normalizeGender(a.gender_audience);
      if (g === "all") counts.all++;
      else if (g === "male") counts.male++;
      else if (g === "female") counts.female++;
    });
    return counts;
  }, [allAds]);

  const adTypeCounts = useMemo(() => {
    const counts = { branding: 0, performance: 0, dts: 0 };
    allAds.forEach(a => {
      if (a.ad_type === "branding") counts.branding++;
      else if (a.ad_type === "performance") counts.performance++;
      else if (a.ad_type === "dts") counts.dts++;
    });
    return counts;
  }, [allAds]);

  const availableCountries = useMemo(() => {
    const map = new Map<string, number>();
    allAds.forEach(a => {
      // Primary: targeted_countries
      const countries = a.targeted_countries || [];
      if (countries.length > 0) {
        countries.forEach(c => map.set(c, (map.get(c) || 0) + 1));
      } else if (a.page_name) {
        // Fallback: extract country hint from page_name (e.g. "Decathlon France" → "FR")
        const pageLower = a.page_name.toLowerCase();
        const COUNTRY_HINTS: Record<string, string> = {
          france: "FR", españa: "ES", espana: "ES", spain: "ES",
          italia: "IT", italy: "IT", deutschland: "DE", germany: "DE",
          portugal: "PT", romania: "RO", românia: "RO", belgique: "BE",
          belgium: "BE", nederland: "NL", netherlands: "NL", polska: "PL",
          poland: "PL", schweiz: "CH", suisse: "CH", österreich: "AT",
          austria: "AT", uk: "GB", "united kingdom": "GB",
        };
        for (const [hint, code] of Object.entries(COUNTRY_HINTS)) {
          if (pageLower.includes(hint)) {
            map.set(code, (map.get(code) || 0) + 1);
            break;
          }
        }
      }
    });
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [allAds]);

  // Apply filters
  const filteredAds = useMemo(() => {
    let result = allAds.filter(ad => {
      if (filterSource.size > 0 && !filterSource.has(normalizeSource(ad.platform))) return false;
      if (filterCompetitors.size > 0 && !filterCompetitors.has(ad.competitor_name)) return false;
      if (filterPlatforms.size > 0 && !getPublisherPlatforms(ad).some(p => filterPlatforms.has(p))) return false;
      if (filterFormats.size > 0 && (!ad.display_format || !filterFormats.has(ad.display_format))) return false;
      if (filterAdvertisers.size > 0) {
        const pname = ad.page_name || "Inconnu";
        if (!filterAdvertisers.has(pname)) return false;
      }
      if (filterStatus === "active" && !ad.is_active) return false;
      if (filterStatus === "inactive" && ad.is_active) return false;
      if (filterDateFrom && ad.start_date && ad.start_date < filterDateFrom) return false;
      if (filterDateTo && ad.start_date && ad.start_date > filterDateTo) return false;
      if (filterGender !== "none" && normalizeGender(ad.gender_audience) !== filterGender) return false;
      if (filterLocations.size > 0) {
        const adLocs = (ad.location_audience || []).map(l => l.name.split(":")[0].trim());
        if (!adLocs.some(l => filterLocations.has(l))) return false;
      }
      if (filterCategories.size > 0 && (!ad.product_category || !filterCategories.has(ad.product_category))) return false;
      if (filterObjectives.size > 0 && (!ad.ad_objective || !filterObjectives.has(ad.ad_objective))) return false;
      if (filterAdType !== "all" && ad.ad_type !== filterAdType) return false;
      if (filterCountry.size > 0) {
        const adCountries = ad.targeted_countries || [];
        let matched = adCountries.some(c => filterCountry.has(c));
        // Fallback: check page_name for country hint
        if (!matched && ad.page_name) {
          const pl = ad.page_name.toLowerCase();
          const HINTS: Record<string, string> = {
            france: "FR", españa: "ES", espana: "ES", italia: "IT",
            deutschland: "DE", portugal: "PT", romania: "RO", românia: "RO",
            belgique: "BE", nederland: "NL", polska: "PL", schweiz: "CH",
            suisse: "CH", österreich: "AT", uk: "GB",
          };
          for (const [hint, code] of Object.entries(HINTS)) {
            if (pl.includes(hint) && filterCountry.has(code)) { matched = true; break; }
          }
        }
        if (!matched) return false;
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const match = (ad.title || "").toLowerCase().includes(q)
          || (ad.ad_text || "").toLowerCase().includes(q)
          || (ad.page_name || "").toLowerCase().includes(q)
          || (ad.link_description || "").toLowerCase().includes(q);
        if (!match) return false;
      }
      return true;
    });
    // Sort: ads with reliable creative_url first, then by start_date descending
    // TikTok signed URLs (tiktokcdn) expire quickly, treat them as no visual
    const hasReliableVisual = (url: string | undefined | null) => {
      if (!url) return false;
      if (url.includes("tiktokcdn")) return false;
      return true;
    };
    result.sort((a, b) => {
      const aHasVisual = hasReliableVisual(a.creative_url) ? 1 : 0;
      const bHasVisual = hasReliableVisual(b.creative_url) ? 1 : 0;
      if (aHasVisual !== bHasVisual) return bHasVisual - aHasVisual;
      const aDate = a.start_date ? new Date(a.start_date).getTime() : 0;
      const bDate = b.start_date ? new Date(b.start_date).getTime() : 0;
      return bDate - aDate;
    });
    return result;
  }, [allAds, filterSource, filterCompetitors, filterPlatforms, filterFormats, filterAdvertisers, filterStatus, filterDateFrom, filterDateTo, filterGender, filterLocations, filterAdType, filterCountry, filterCategories, filterObjectives, searchQuery]);

  // Reset pagination when filters change
  useEffect(() => { setVisibleCount(12); }, [filterSource, filterCompetitors, filterPlatforms, filterFormats, filterAdvertisers, filterStatus, filterDateFrom, filterDateTo, filterGender, filterLocations, filterAdType, filterCountry, filterCategories, filterObjectives, searchQuery]);

  const visibleAds = useMemo(() => filteredAds.slice(0, visibleCount), [filteredAds, visibleCount]);
  const hasMoreAds = visibleCount < filteredAds.length;

  // Filtered stats
  const activeFilters = filterSource.size + filterCompetitors.size + filterPlatforms.size + filterFormats.size + filterAdvertisers.size
    + (filterStatus !== "all" ? 1 : 0) + (searchQuery ? 1 : 0)
    + (filterGender !== "none" ? 1 : 0) + filterLocations.size
    + (filterAdType !== "all" ? 1 : 0) + filterCountry.size
    + filterCategories.size + filterObjectives.size;

  const stats = useMemo(() => {
    const active = filteredAds.filter(a => a.is_active).length;
    const byCompetitor = new Map<string, { total: number; active: number; spendMin: number; spendMax: number }>();
    const byAdvertiser = new Map<string, { total: number; active: number; likes?: number; categories?: string[]; logo?: string; spendMin: number; spendMax: number }>();
    const bySource = new Map<string, { spendMin: number; spendMax: number; count: number }>();
    const byFormat = new Map<string, number>();
    const byPlatform = new Map<string, number>();
    const competitorPlatforms = new Map<string, Map<string, number>>();
    let totalDurationDays = 0;
    let durationCount = 0;
    let totalSpendMin = 0;
    let totalSpendMax = 0;
    let totalImpressions = 0;
    let totalReach = 0;

    filteredAds.forEach(a => {
      // Per-ad spend (actual or CPM-estimated)
      let adSpendMin = a.estimated_spend_min || 0;
      let adSpendMax = a.estimated_spend_max || 0;
      if (adSpendMin === 0 && adSpendMax === 0) {
        const budget = estimateBudget(a);
        if (budget) { adSpendMin = budget.min; adSpendMax = budget.max; }
      }
      totalSpendMin += adSpendMin;
      totalSpendMax += adSpendMax;

      // By source (channel)
      const src = normalizeSource(a.platform);
      const ss = bySource.get(src) || { spendMin: 0, spendMax: 0, count: 0 };
      ss.spendMin += adSpendMin; ss.spendMax += adSpendMax; ss.count++;
      bySource.set(src, ss);

      // By competitor
      const cc = byCompetitor.get(a.competitor_name) || { total: 0, active: 0, spendMin: 0, spendMax: 0 };
      cc.total++;
      if (a.is_active) cc.active++;
      cc.spendMin += adSpendMin;
      cc.spendMax += adSpendMax;
      byCompetitor.set(a.competitor_name, cc);

      // By advertiser (page name)
      const pn = a.page_name || "Inconnu";
      const aa = byAdvertiser.get(pn) || { total: 0, active: 0, likes: 0, categories: [], logo: undefined, spendMin: 0, spendMax: 0 };
      aa.total++;
      if (a.is_active) aa.active++;
      if (a.page_like_count && a.page_like_count > (aa.likes || 0)) aa.likes = a.page_like_count;
      // Always use competitor logo_url
      const compLogo = competitors.find(c => c.name.toLowerCase() === (a.competitor_name || "").toLowerCase())?.logo_url;
      if (!aa.logo) aa.logo = compLogo;
      if (a.page_categories) {
        a.page_categories.forEach(c => { if (!aa.categories!.includes(c)) aa.categories!.push(c); });
      }
      aa.spendMin += adSpendMin;
      aa.spendMax += adSpendMax;
      byAdvertiser.set(pn, aa);

      // By format
      const fmt = a.display_format || "UNKNOWN";
      byFormat.set(fmt, (byFormat.get(fmt) || 0) + 1);

      // By platform
      getPublisherPlatforms(a).forEach(p => byPlatform.set(p, (byPlatform.get(p) || 0) + 1));

      // Competitor x platform matrix
      if (!competitorPlatforms.has(a.competitor_name)) competitorPlatforms.set(a.competitor_name, new Map());
      const cpMap = competitorPlatforms.get(a.competitor_name)!;
      getPublisherPlatforms(a).forEach(p => cpMap.set(p, (cpMap.get(p) || 0) + 1));

      // Impressions & reach
      if (a.impressions_min && a.impressions_min > 0) totalImpressions += a.impressions_min;
      if (a.eu_total_reach && a.eu_total_reach > 0) totalReach += a.eu_total_reach;

      // Duration stats — only count ads with both start and end dates for accurate average
      if (a.start_date && a.end_date) {
        const start = new Date(a.start_date);
        const end = new Date(a.end_date);
        const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
        if (days > 0) { totalDurationDays += days; durationCount++; }
      }
    });

    const avgDuration = durationCount > 0 ? Math.round(totalDurationDays / durationCount) : 0;

    return { active, byCompetitor, byAdvertiser, bySource, byFormat, byPlatform, competitorPlatforms, avgDuration, totalSpendMin, totalSpendMax, totalImpressions, totalReach };
  }, [filteredAds]);

  function toggleExpand(adId: string) {
    setExpandedAds(prev => {
      const next = new Set(prev);
      if (next.has(adId)) next.delete(adId); else next.add(adId);
      return next;
    });
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement des publicit&eacute;s...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Header ─────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 sm:h-11 sm:w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50 shrink-0">
            <Megaphone className="h-5 w-5 text-violet-600" />
          </div>
          <div className="min-w-0">
            <h1 className="text-lg sm:text-xl font-bold tracking-tight text-foreground">Cockpit Publicitaire</h1>
            <p className="text-[12px] sm:text-[13px] text-muted-foreground truncate">
              Meta, TikTok &amp; Google Ads
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
          <PeriodFilter selectedDays={periodDays} onDaysChange={handlePeriodChange} />
          <Button variant="outline" size="sm" onClick={handleFetchAll} disabled={fetching} className="gap-2">
            <RefreshCw className={`h-3.5 w-3.5 ${fetching ? "animate-spin" : ""}`} />
            Scanner tout
          </Button>
        </div>
      </div>

      {/* ── KPI Banner ─────────────────────── */}
      <div className="rounded-2xl bg-gradient-to-r from-indigo-950 via-[#1e1b4b] to-violet-950 px-4 sm:px-8 py-5 sm:py-6 text-white relative overflow-hidden">
        <div className="absolute -top-16 -right-16 h-48 w-48 rounded-full bg-violet-400/[0.05]" />
        <div className="absolute -bottom-10 -left-10 h-32 w-32 rounded-full bg-indigo-400/[0.04]" />
        <div className="relative grid grid-cols-3 sm:grid-cols-5 gap-4 sm:gap-6">
          <div>
            <div className="text-2xl sm:text-3xl font-bold tabular-nums">{filteredAds.length}</div>
            <div className="text-[10px] sm:text-[11px] text-violet-300/60 uppercase tracking-widest mt-0.5">
              {activeFilters > 0 ? "Filtr\u00E9es" : "Pubs"}
            </div>
            <InfoTooltip text={METHODOLOGY.platforms} className="mt-0.5" light />
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-bold tabular-nums text-emerald-400">{stats.active}</div>
            <div className="flex items-center gap-1 text-[10px] sm:text-[11px] text-violet-300/60 uppercase tracking-widest mt-0.5">Actives <InfoTooltip text={METHODOLOGY.activeAds} light /></div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-bold tabular-nums">{stats.byAdvertiser.size}</div>
            <div className="text-[10px] sm:text-[11px] text-violet-300/60 uppercase tracking-widest mt-0.5">Payeurs</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-bold tabular-nums">{stats.byCompetitor.size}</div>
            <div className="text-[10px] sm:text-[11px] text-violet-300/60 uppercase tracking-widest mt-0.5">Concurrents</div>
          </div>
          <div>
            <div className="text-2xl sm:text-3xl font-bold tabular-nums">{stats.avgDuration}<span className="text-base sm:text-lg font-normal text-violet-300/50">j</span></div>
            <div className="flex items-center gap-1 text-[10px] sm:text-[11px] text-violet-300/60 uppercase tracking-widest mt-0.5">Dur. moy. <InfoTooltip text={METHODOLOGY.duration} light /></div>
          </div>
          {stats.totalSpendMax > 0 && (
            <div className="col-span-2">
              <div className="text-xl sm:text-2xl font-bold tabular-nums text-emerald-400">
                {formatNumber(stats.totalSpendMin)}&ndash;{formatNumber(stats.totalSpendMax)}<span className="text-base sm:text-lg font-normal text-emerald-300/50">&euro;</span>
              </div>
              <div className="flex items-center gap-1 text-[10px] sm:text-[11px] text-violet-300/60 uppercase tracking-widest mt-0.5">Budget total <InfoTooltip text={METHODOLOGY.budget} light /></div>
            </div>
          )}
          {/* Platform breakdown with icons */}
          {stats.byPlatform.size > 0 && (
            <div className="col-span-3 sm:col-span-2 flex items-center gap-2 sm:gap-3">
              {Array.from(stats.byPlatform.entries()).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([p, count]) => (
                <div key={p} className="text-center flex flex-col items-center gap-1">
                  <div className="h-6 w-6 sm:h-7 sm:w-7 rounded-lg bg-white/[0.08] sm:backdrop-blur-sm flex items-center justify-center border border-white/[0.06]">
                    <PlatformIcon name={p} className="h-3 w-3 sm:h-3.5 sm:w-3.5 text-white/80" />
                  </div>
                  <div className="text-xs sm:text-sm font-semibold tabular-nums">{count}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Channel pills ─────────────────────── */}
      {availableSources.entries.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground mr-1">Canal</span>
          <button
            onClick={() => setFilterSource(new Set())}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              filterSource.size === 0
                ? "bg-foreground text-background shadow-sm"
                : "bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            }`}
          >
            Tous
            <span className={`text-[10px] tabular-nums ${filterSource.size === 0 ? "text-background/70" : "text-muted-foreground/60"}`}>{availableSources.total}</span>
          </button>
          {availableSources.entries.map(([src, count]) => {
            const cfg = SOURCE_CONFIG[src] || { label: src, icon: null };
            const active = filterSource.has(src);
            return (
              <button
                key={src}
                onClick={() => toggleFilter(filterSource, src, setFilterSource)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  active
                    ? "bg-foreground text-background shadow-sm"
                    : "bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                }`}
              >
                {cfg.icon}
                {cfg.label}
                <span className={`text-[10px] tabular-nums ${active ? "text-background/70" : "text-muted-foreground/60"}`}>{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Budget by channel donut ─────────────── */}
      {stats.totalSpendMax > 0 && stats.bySource.size > 0 && (() => {
        const donutData = Array.from(stats.bySource.entries())
          .map(([src, d]) => ({
            name: SOURCE_CONFIG[src]?.label || src,
            value: Math.round((d.spendMin + d.spendMax) / 2),
            color: SOURCE_CONFIG[src]?.color || "#94a3b8",
            count: d.count,
            min: d.spendMin,
            max: d.spendMax,
          }))
          .filter(d => d.value > 0)
          .sort((a, b) => b.value - a.value);
        if (donutData.length === 0) return null;
        const total = donutData.reduce((s, d) => s + d.value, 0);
        return (
          <div className="rounded-2xl border bg-card p-5">
            <div className="flex items-center gap-2.5 mb-4">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900">
                <PieChart className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <h3 className="text-[12px] font-semibold text-foreground">Budget par canal</h3>
                <p className="text-[10px] text-muted-foreground">Estimation basée sur le CPM par levier{filterAdvertisers.size > 0 ? ` · ${filterAdvertisers.size} annonceur${filterAdvertisers.size > 1 ? "s" : ""} sélectionné${filterAdvertisers.size > 1 ? "s" : ""}` : ""}</p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="w-36 h-36 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <RechartsPie>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={38}
                      outerRadius={65}
                      paddingAngle={2}
                      dataKey="value"
                      stroke="none"
                    >
                      {donutData.map((d, i) => (
                        <Cell key={i} fill={d.color} />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      formatter={(value: number) => `${formatNumber(value)} €`}
                      contentStyle={{ borderRadius: "0.75rem", fontSize: "12px", border: "1px solid var(--border)" }}
                    />
                  </RechartsPie>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-2.5">
                {donutData.map(d => {
                  const pct = total > 0 ? Math.round((d.value / total) * 100) : 0;
                  return (
                    <div key={d.name} className="flex items-center gap-3">
                      <div className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: d.color }} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium">{d.name}</span>
                          <span className="text-xs font-bold tabular-nums">{pct}%</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-muted mt-1 overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: d.color }} />
                        </div>
                        <div className="flex items-center justify-between mt-0.5">
                          <span className="text-[10px] text-muted-foreground">{d.count} pub{d.count > 1 ? "s" : ""}</span>
                          <span className="text-[10px] text-muted-foreground tabular-nums">{formatNumber(d.min)}–{formatNumber(d.max)} €</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        );
      })()}


      {/* ── Filters (collapsible, closed by default) ─ */}
      <div className="rounded-2xl border bg-card overflow-hidden">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="w-full flex items-center justify-between px-5 py-3 hover:bg-muted/30 transition-colors"
        >
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
            <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Filtres & Recherche
            </span>
            {activeFilters > 0 && (
              <span className="inline-flex items-center justify-center h-5 w-5 rounded-full bg-blue-600 text-white text-[10px] font-bold">
                {activeFilters}
              </span>
            )}
            {activeFilters > 0 && !showFilters && (
              <span className="text-[10px] text-blue-600 font-medium ml-1">
                {filteredAds.length} resultat{filteredAds.length > 1 ? "s" : ""}
              </span>
            )}
          </div>
          {showFilters ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </button>

        {showFilters && (
          <div className="px-5 pb-5 space-y-4 border-t">
            {/* Search */}
            <div className="pt-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Rechercher dans les pubs (titre, texte, annonceur...)"
                  className="w-full pl-10 pr-10 py-2.5 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-400"
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>

            {/* Row 1: Period + Status + Gender (compact) */}
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Période</span>
                </div>
                <DateRangeFilter
                  dateFrom={filterDateFrom}
                  dateTo={filterDateTo}
                  onDateFromChange={setFilterDateFrom}
                  onDateToChange={setFilterDateTo}
                />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Statut</span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <FilterChip label="Toutes" active={filterStatus === "all"} onClick={() => setFilterStatus("all")} />
                  <FilterChip label="Actives" active={filterStatus === "active"} onClick={() => setFilterStatus("active")} count={allAds.filter(a => a.is_active).length} />
                  <FilterChip label="Termin&eacute;es" active={filterStatus === "inactive"} onClick={() => setFilterStatus("inactive")} count={allAds.filter(a => !a.is_active).length} />
                </div>
              </div>
              {(genderCounts.all > 0 || genderCounts.male > 0 || genderCounts.female > 0) && (
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <UserCheck className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Genre cible</span>
                    <InfoTooltip text={METHODOLOGY.gender} />
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <FilterChip label="Tous" active={filterGender === "none"} onClick={() => setFilterGender("none")} />
                    {genderCounts.all > 0 && <FilterChip label="Mixte" count={genderCounts.all} active={filterGender === "all"} onClick={() => setFilterGender(filterGender === "all" ? "none" : "all")} />}
                    {genderCounts.male > 0 && <FilterChip label="Hommes" count={genderCounts.male} active={filterGender === "male"} onClick={() => setFilterGender(filterGender === "male" ? "none" : "male")} />}
                    {genderCounts.female > 0 && <FilterChip label="Femmes" count={genderCounts.female} active={filterGender === "female"} onClick={() => setFilterGender(filterGender === "female" ? "none" : "female")} />}
                  </div>
                </div>
              )}
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Target className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Type de pub</span>
                  <InfoTooltip text="Segmentation automatique : Branding (notoriete), Performance (conversion/achat), Drive-to-Store (trafic en magasin)." />
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <FilterChip label="Tous" active={filterAdType === "all"} onClick={() => setFilterAdType("all")} />
                  <FilterChip label="Branding" active={filterAdType === "branding"} onClick={() => setFilterAdType(filterAdType === "branding" ? "all" : "branding")} count={adTypeCounts.branding} icon={<Megaphone className="h-3 w-3" />} />
                  <FilterChip label="Performance" active={filterAdType === "performance"} onClick={() => setFilterAdType(filterAdType === "performance" ? "all" : "performance")} count={adTypeCounts.performance} icon={<TrendingUp className="h-3 w-3" />} />
                  <FilterChip label="Drive-to-Store" active={filterAdType === "dts"} onClick={() => setFilterAdType(filterAdType === "dts" ? "all" : "dts")} count={adTypeCounts.dts} icon={<MapPin className="h-3 w-3" />} />
                </div>
              </div>
            </div>

            {/* Country filter */}
            {availableCountries.length > 1 && (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Globe className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Pays</span>
                  <InfoTooltip text="Pays cible des publicites (targeted_countries Meta) ou detecte depuis le nom de la page (ex: Decathlon France = FR)." />
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {availableCountries.map(([code, count]) => (
                    <FilterChip key={code} label={COUNTRY_LABELS[code] || code} count={count} active={filterCountry.has(code)} onClick={() => toggleFilter(filterCountry, code, setFilterCountry)} />
                  ))}
                </div>
              </div>
            )}

            {/* Row 2: Concurrent + Platform + Format (bounded) */}
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Users className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Concurrent</span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {availableCompetitors.map(([name, count]) => (
                    <span key={name} className="inline-flex items-center">
                      <FilterChip label={name} count={count} active={filterCompetitors.has(name)} onClick={() => toggleFilter(filterCompetitors, name, setFilterCompetitors)} />
                      {!!(brandName && name.toLowerCase() === brandName.toLowerCase()) && <span className="ml-1 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Monitor className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Plateforme</span>
                    <InfoTooltip text={METHODOLOGY.platforms} />
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {availablePlatforms.map(([name, count]) => (
                    <FilterChip key={name} label={PLATFORM_CONFIGS[name]?.label || name.toLowerCase().replace("_", " ")} count={count} active={filterPlatforms.has(name)} onClick={() => toggleFilter(filterPlatforms, name, setFilterPlatforms)} icon={<PlatformIcon name={name} className="h-3.5 w-3.5" />} />
                  ))}
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Layers className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Format</span>
                    <InfoTooltip text={METHODOLOGY.formats} />
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {availableFormats.map(([name, count]) => (
                    <FilterChip key={name} label={FORMAT_LABELS[name]?.label || name} count={count} active={filterFormats.has(name)} onClick={() => toggleFilter(filterFormats, name, setFilterFormats)} />
                  ))}
                </div>
              </div>
            </div>

            {/* Row 3: Annonceur + Lieu - collapsible with search */}
            <div className="grid gap-4 sm:grid-cols-2">
              {/* Annonceur - collapsible */}
              {availableAdvertisers.length > 0 && (
                <div className="rounded-xl border bg-muted/20 overflow-hidden">
                  <button
                    onClick={() => setExpandedFilterSections(prev => { const n = new Set(prev); if (n.has("advertiser")) n.delete("advertiser"); else n.add("advertiser"); return n; })}
                    className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Annonceur</span>
                      <span className="text-[10px] text-muted-foreground tabular-nums">{availableAdvertisers.length}</span>
                      {filterAdvertisers.size > 0 && (
                        <span className="inline-flex items-center justify-center h-4 min-w-[16px] rounded-full bg-violet-600 text-white text-[9px] font-bold px-1">{filterAdvertisers.size}</span>
                      )}
                    </div>
                    {expandedFilterSections.has("advertiser") ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                  </button>
                  {expandedFilterSections.has("advertiser") && (
                    <div className="px-3.5 pb-3 space-y-2">
                      {availableAdvertisers.length > 6 && (
                        <div className="relative">
                          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                          <input
                            type="text"
                            value={advertiserSearch}
                            onChange={(e) => setAdvertiserSearch(e.target.value)}
                            placeholder="Filtrer les annonceurs..."
                            className="w-full pl-7 pr-7 py-1.5 rounded-lg border bg-background text-xs focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                          />
                          {advertiserSearch && (
                            <button onClick={() => setAdvertiserSearch("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                              <X className="h-3 w-3" />
                            </button>
                          )}
                        </div>
                      )}
                      <div className="max-h-48 overflow-y-auto space-y-0.5 pr-1">
                        {availableAdvertisers
                          .filter(([name]) => !advertiserSearch || name.toLowerCase().includes(advertiserSearch.toLowerCase()))
                          .map(([name, count]) => {
                            const logo = advertiserLogos.get(name);
                            const active = filterAdvertisers.has(name);
                            return (
                              <button
                                key={name}
                                onClick={() => toggleFilter(filterAdvertisers, name, setFilterAdvertisers)}
                                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left transition-colors ${active ? "bg-violet-100 text-violet-800" : "hover:bg-muted/60"}`}
                              >
                                <div className={`flex items-center justify-center h-4 w-4 rounded border shrink-0 ${active ? "bg-violet-600 border-violet-600 text-white" : "border-border bg-background"}`}>
                                  {active && <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>}
                                </div>
                                {logo ? (
                                  // eslint-disable-next-line @next/next/no-img-element
                                  <img src={logo} alt="" className="h-5 w-5 rounded-full object-cover shrink-0" />
                                ) : (
                                  <div className="h-5 w-5 rounded-full bg-muted flex items-center justify-center shrink-0">
                                    <span className="text-[8px] font-bold text-muted-foreground">{name.slice(0, 2).toUpperCase()}</span>
                                  </div>
                                )}
                                <span className="text-xs font-medium truncate flex-1">{name}</span>
                                <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">{count}</span>
                              </button>
                            );
                          })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Lieu de diffusion - collapsible with search */}
              {availableLocations.length > 0 && (
                <div className="rounded-xl border bg-muted/20 overflow-hidden">
                  <button
                    onClick={() => setExpandedFilterSections(prev => { const n = new Set(prev); if (n.has("location")) n.delete("location"); else n.add("location"); return n; })}
                    className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-muted/30 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Lieu de diffusion</span>
                      <span className="text-[10px] text-muted-foreground tabular-nums">{availableLocations.length}</span>
                      {filterLocations.size > 0 && (
                        <span className="inline-flex items-center justify-center h-4 min-w-[16px] rounded-full bg-violet-600 text-white text-[9px] font-bold px-1">{filterLocations.size}</span>
                      )}
                    </div>
                    {expandedFilterSections.has("location") ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                  </button>
                  {expandedFilterSections.has("location") && (
                    <div className="px-3.5 pb-3 space-y-2">
                      <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                        <input
                          type="text"
                          value={locationSearch}
                          onChange={(e) => setLocationSearch(e.target.value)}
                          placeholder="Rechercher un lieu..."
                          className="w-full pl-7 pr-7 py-1.5 rounded-lg border bg-background text-xs focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                        />
                        {locationSearch && (
                          <button onClick={() => setLocationSearch("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                            <X className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                      <div className="max-h-48 overflow-y-auto space-y-0.5 pr-1">
                        {availableLocations
                          .filter(([name]) => !locationSearch || name.toLowerCase().includes(locationSearch.toLowerCase()))
                          .map(([name, count]) => {
                            const active = filterLocations.has(name);
                            const isCountry = !name.includes(",") && !/^\d/.test(name);
                            return (
                              <button
                                key={name}
                                onClick={() => toggleFilter(filterLocations, name, setFilterLocations)}
                                className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left transition-colors ${active ? "bg-violet-100 text-violet-800" : "hover:bg-muted/60"}`}
                              >
                                <div className={`flex items-center justify-center h-4 w-4 rounded border shrink-0 ${active ? "bg-violet-600 border-violet-600 text-white" : "border-border bg-background"}`}>
                                  {active && <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>}
                                </div>
                                <span className={`text-xs truncate flex-1 ${isCountry ? "font-semibold" : "font-medium"}`}>{name}</span>
                                <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">{count}</span>
                              </button>
                            );
                          })}
                        {availableLocations.filter(([name]) => !locationSearch || name.toLowerCase().includes(locationSearch.toLowerCase())).length === 0 && (
                          <div className="text-xs text-muted-foreground text-center py-3">Aucun lieu trouv&eacute;</div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Row 4: Catégorie produit + Objectif pub — only shown if any ads have these fields */}
            {(availableCategories.length > 0 || availableObjectives.length > 0) && (
              <div className="grid gap-4 sm:grid-cols-2">
                {/* Catégorie produit - collapsible with search */}
                {availableCategories.length > 0 && (
                  <div className="rounded-xl border bg-muted/20 overflow-hidden">
                    <button
                      onClick={() => setExpandedFilterSections(prev => { const n = new Set(prev); if (n.has("category")) n.delete("category"); else n.add("category"); return n; })}
                      className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Tag className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Cat&eacute;gorie produit</span>
                        <span className="text-[10px] text-muted-foreground tabular-nums">{availableCategories.length}</span>
                        {filterCategories.size > 0 && (
                          <span className="inline-flex items-center justify-center h-4 min-w-[16px] rounded-full bg-violet-600 text-white text-[9px] font-bold px-1">{filterCategories.size}</span>
                        )}
                      </div>
                      {expandedFilterSections.has("category") ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                    </button>
                    {expandedFilterSections.has("category") && (
                      <div className="px-3.5 pb-3 space-y-2">
                        {availableCategories.length > 6 && (
                          <div className="relative">
                            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
                            <input
                              type="text"
                              value={categorySearch}
                              onChange={(e) => setCategorySearch(e.target.value)}
                              placeholder="Filtrer les cat&eacute;gories..."
                              className="w-full pl-7 pr-7 py-1.5 rounded-lg border bg-background text-xs focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                            />
                            {categorySearch && (
                              <button onClick={() => setCategorySearch("")} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                                <X className="h-3 w-3" />
                              </button>
                            )}
                          </div>
                        )}
                        <div className="max-h-48 overflow-y-auto space-y-0.5 pr-1">
                          {availableCategories
                            .filter(([name]) => !categorySearch || name.toLowerCase().includes(categorySearch.toLowerCase()))
                            .map(([name, count]) => {
                              const active = filterCategories.has(name);
                              return (
                                <button
                                  key={name}
                                  onClick={() => toggleFilter(filterCategories, name, setFilterCategories)}
                                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-left transition-colors ${active ? "bg-violet-100 text-violet-800" : "hover:bg-muted/60"}`}
                                >
                                  <div className={`flex items-center justify-center h-4 w-4 rounded border shrink-0 ${active ? "bg-violet-600 border-violet-600 text-white" : "border-border bg-background"}`}>
                                    {active && <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>}
                                  </div>
                                  <span className="text-xs font-medium truncate flex-1">{name}</span>
                                  <span className="text-[10px] text-muted-foreground tabular-nums shrink-0">{count}</span>
                                </button>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Objectif pub */}
                {availableObjectives.length > 0 && (
                  <div className="rounded-xl border bg-muted/20 overflow-hidden">
                    <button
                      onClick={() => setExpandedFilterSections(prev => { const n = new Set(prev); if (n.has("objective")) n.delete("objective"); else n.add("objective"); return n; })}
                      className="w-full flex items-center justify-between px-3.5 py-2.5 hover:bg-muted/30 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Target className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Objectif pub</span>
                        <span className="text-[10px] text-muted-foreground tabular-nums">{availableObjectives.length}</span>
                        {filterObjectives.size > 0 && (
                          <span className="inline-flex items-center justify-center h-4 min-w-[16px] rounded-full bg-violet-600 text-white text-[9px] font-bold px-1">{filterObjectives.size}</span>
                        )}
                      </div>
                      {expandedFilterSections.has("objective") ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
                    </button>
                    {expandedFilterSections.has("objective") && (
                      <div className="px-3.5 pb-3">
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {availableObjectives.map(([name, count]) => (
                            <FilterChip key={name} label={name} count={count} active={filterObjectives.has(name)} onClick={() => toggleFilter(filterObjectives, name, setFilterObjectives)} />
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Clear all */}
            {activeFilters > 0 && (
              <div className="flex items-center justify-between pt-1">
                <button
                  onClick={clearAllFilters}
                  className="flex items-center gap-1.5 text-xs text-red-500 hover:text-red-600 font-medium transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                  Effacer tous les filtres ({activeFilters})
                </button>
                <span className="text-[11px] text-muted-foreground tabular-nums">
                  {filteredAds.length} r&eacute;sultat{filteredAds.length > 1 ? "s" : ""}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Demographics Panel ────────────── */}
      <DemographicsPanel filteredAds={filteredAds} />

      {/* ── Insights Strategiques ────── */}
      <InsightsSection filteredAds={filteredAds} stats={stats} />

      {/* ── Comparatif Concurrentiel ── */}
      <CompetitorComparison filteredAds={filteredAds} stats={stats} competitors={competitors} brandName={brandName} />

      {/* ── Creative Intelligence ─────────────────── */}
      <div className="rounded-2xl border bg-card overflow-hidden">
        <div className="px-5 py-4 flex items-center justify-between border-b">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-900">
              <Brain className="h-3.5 w-3.5 text-violet-600 dark:text-violet-400" />
            </div>
            <div>
              <h3 className="text-[12px] font-semibold text-foreground">Intelligence Cr&eacute;ative</h3>
              <p className="text-[10px] text-muted-foreground">
                Analyse IA des visuels publicitaires
                {creativeInsights && creativeInsights.total_analyzed > 0 && (
                  <> &middot; {creativeInsights.total_analyzed} analys&eacute;e{creativeInsights.total_analyzed > 1 ? "s" : ""}</>
                )}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleAnalyzeCreatives}
            disabled={analyzingCreatives}
            className="gap-2 text-xs"
          >
            {analyzingCreatives ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
            {analyzingCreatives ? "Analyse en cours..." : "Analyser les visuels"}
          </Button>
        </div>

        {analyzeResult && (
          <div className="px-5 py-2.5 bg-muted/30 border-b text-[11px]">
            <span className="text-emerald-600 font-semibold">{analyzeResult.analyzed} analys&eacute;e{analyzeResult.analyzed > 1 ? "s" : ""}</span>
            {analyzeResult.errors > 0 && <span className="text-red-500 ml-2">{analyzeResult.errors} erreur{analyzeResult.errors > 1 ? "s" : ""}</span>}
            {analyzeResult.remaining > 0 && <span className="text-muted-foreground ml-2">&middot; {analyzeResult.remaining} restante{analyzeResult.remaining > 1 ? "s" : ""}</span>}
          </div>
        )}

        {creativeInsights && creativeInsights.total_analyzed > 0 ? (
          <div className="p-5 space-y-5">
            {/* Score moyen + KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 rounded-xl bg-gradient-to-br from-violet-50 to-indigo-50 border border-violet-100 text-center">
                <div className="text-2xl font-bold text-violet-700">{creativeInsights.avg_score}</div>
                <div className="text-[10px] text-violet-500 uppercase tracking-widest mt-0.5">Score moyen</div>
              </div>
              <div className="p-3 rounded-xl bg-muted/50 text-center">
                <div className="text-2xl font-bold">{creativeInsights.total_analyzed}</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-widest mt-0.5">Analys&eacute;es</div>
              </div>
              <div className="p-3 rounded-xl bg-muted/50 text-center">
                <div className="text-2xl font-bold">{creativeInsights.concepts.length}</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-widest mt-0.5">Concepts</div>
              </div>
              <div className="p-3 rounded-xl bg-muted/50 text-center">
                <div className="text-2xl font-bold">{creativeInsights.by_competitor.length}</div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-widest mt-0.5">B&eacute;n&eacute;ficiaires</div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Top concepts */}
              {creativeInsights.concepts.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">Concepts dominants</div>
                  <div className="space-y-2">
                    {creativeInsights.concepts.slice(0, 6).map(c => (
                      <div key={c.concept} className="flex items-center gap-3">
                        <span className="text-xs font-medium w-24 truncate">{c.concept}</span>
                        <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                          <div className="h-full rounded-full bg-violet-500 transition-all duration-500" style={{ width: `${c.pct}%` }} />
                        </div>
                        <span className="text-[10px] font-bold tabular-nums w-10 text-right">{c.pct}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Top tones */}
              {creativeInsights.tones.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">Tons utilis&eacute;s</div>
                  <div className="space-y-2">
                    {creativeInsights.tones.slice(0, 6).map(t => (
                      <div key={t.tone} className="flex items-center gap-3">
                        <span className="text-xs font-medium w-24 truncate">{t.tone}</span>
                        <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                          <div className="h-full rounded-full bg-pink-500 transition-all duration-500" style={{ width: `${t.pct}%` }} />
                        </div>
                        <span className="text-[10px] font-bold tabular-nums w-10 text-right">{t.pct}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Product categories + Objectives */}
            {((creativeInsights.categories && creativeInsights.categories.length > 0) || (creativeInsights.objectives && creativeInsights.objectives.length > 0)) && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {/* Product categories */}
                {creativeInsights.categories && creativeInsights.categories.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">Cat&eacute;gories produit</div>
                    <div className="space-y-2">
                      {creativeInsights.categories.slice(0, 8).map(c => (
                        <div key={c.category} className="flex items-center gap-3">
                          <span className="text-xs font-medium w-32 truncate">{c.category}</span>
                          <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                            <div className="h-full rounded-full bg-emerald-500 transition-all duration-500" style={{ width: `${c.pct}%` }} />
                          </div>
                          <span className="text-[10px] font-bold tabular-nums w-10 text-right">{c.pct}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Ad objectives */}
                {creativeInsights.objectives && creativeInsights.objectives.length > 0 && (
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">Objectifs publicitaires</div>
                    <div className="space-y-2">
                      {creativeInsights.objectives.slice(0, 8).map(o => (
                        <div key={o.objective} className="flex items-center gap-3">
                          <span className="text-xs font-medium w-32 truncate">{o.objective}</span>
                          <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                            <div className="h-full rounded-full bg-sky-500 transition-all duration-500" style={{ width: `${o.pct}%` }} />
                          </div>
                          <span className="text-[10px] font-bold tabular-nums w-10 text-right">{o.pct}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Color palette + by competitor */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Color trends */}
              {creativeInsights.colors.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">Palette couleurs tendance</div>
                  <div className="flex flex-wrap gap-2">
                    {creativeInsights.colors.slice(0, 12).map(c => (
                      <div key={c.color} className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-muted/50 border">
                        <div className="h-4 w-4 rounded-full border border-gray-200" style={{ backgroundColor: c.color }} />
                        <span className="text-[10px] font-mono text-muted-foreground">{c.color}</span>
                        <span className="text-[9px] font-bold text-muted-foreground/60">{c.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Score par concurrent */}
              {creativeInsights.by_competitor.length > 0 && (
                <div>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">Score par concurrent</div>
                  <div className="space-y-2">
                    {creativeInsights.by_competitor.map((c, i) => {
                      const isBrand = !!(brandName && c.competitor.toLowerCase() === brandName.toLowerCase());
                      return (
                      <div key={c.competitor} className={`flex items-center gap-3 ${isBrand ? "bg-violet-50/50 ring-1 ring-violet-200 rounded-lg px-2 py-1" : ""}`}>
                        <span className="text-[10px] font-bold text-muted-foreground/50 w-4">{i + 1}</span>
                        <span className="text-xs font-medium flex-1 truncate">{c.competitor}{isBrand && <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}</span>
                        <span className="text-[10px] text-muted-foreground">{c.count} pubs</span>
                        <span className={`text-xs font-bold tabular-nums ${c.avg_score >= 70 ? "text-emerald-600" : c.avg_score >= 50 ? "text-blue-600" : "text-amber-600"}`}>
                          {c.avg_score}
                        </span>
                      </div>
                      ); })}
                  </div>
                </div>
              )}
            </div>

            {/* Top performers */}
            {creativeInsights.top_performers.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">
                  <Trophy className="h-3 w-3 inline mr-1" />Top cr&eacute;atifs
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                  {creativeInsights.top_performers.slice(0, 5).map((p) => (
                    <div key={p.ad_id} className="rounded-xl border overflow-hidden bg-muted/20 hover:shadow-md transition-shadow">
                      {p.creative_url && (
                        <div className="aspect-square bg-slate-900 overflow-hidden flex items-center justify-center relative">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={p.creative_url} alt="" loading="lazy" className="max-w-full max-h-full object-contain" />
                          <div className="absolute top-2 right-2">
                            <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold shadow-sm ${
                              p.score >= 80 ? "bg-emerald-500 text-white" :
                              p.score >= 60 ? "bg-blue-500 text-white" :
                              "bg-amber-500 text-white"
                            }`}>
                              <Sparkles className="h-2 w-2" />{p.score}
                            </span>
                          </div>
                        </div>
                      )}
                      <div className="p-2">
                        <div className="text-[10px] font-semibold truncate">{p.competitor_name}{!!(brandName && p.competitor_name?.toLowerCase() === brandName.toLowerCase()) && <span className="ml-1 text-[9px] bg-violet-100 text-violet-600 px-1.5 py-0.5 rounded-full uppercase tracking-wider font-bold">Vous</span>}</div>
                        <div className="flex items-center gap-1 mt-0.5">
                          {p.concept && <span className="text-[9px] px-1.5 py-0 rounded bg-violet-100 text-violet-700">{p.concept}</span>}
                          {p.tone && <span className="text-[9px] px-1.5 py-0 rounded bg-pink-100 text-pink-700">{p.tone}</span>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {creativeInsights.recommendations.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold mb-2.5">
                  <Lightbulb className="h-3 w-3 inline mr-1" />Recommandations
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {creativeInsights.recommendations.map((r, i) => (
                    <div key={i} className="flex gap-2.5 p-3 rounded-xl bg-gradient-to-br from-violet-50/50 to-indigo-50/50 border border-violet-100">
                      <Sparkles className="h-4 w-4 text-violet-500 shrink-0 mt-0.5" />
                      <p className="text-xs text-foreground/80 leading-relaxed">{r}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="px-5 py-8 text-center">
            <Brain className="h-8 w-8 text-muted-foreground/20 mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              Aucune analyse cr&eacute;ative. Cliquez sur &laquo;&nbsp;Analyser les visuels&nbsp;&raquo; pour d&eacute;marrer.
            </p>
          </div>
        )}
      </div>

      {/* ── Payeurs & Diffusion ────── */}
      {stats.byAdvertiser.size > 0 && (() => {
        const sortedAdvertisers = Array.from(stats.byAdvertiser.entries()).sort((a, b) => b[1].total - a[1].total);
        const PAYER_LIMIT = 5;
        const hasMore = sortedAdvertisers.length > PAYER_LIMIT;
        const visibleAdvertisers = showAllPayers ? sortedAdvertisers : sortedAdvertisers.slice(0, PAYER_LIMIT);
        return (
          <div className="rounded-2xl border bg-card/50 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-100">
                  <Building2 className="h-4.5 w-4.5 text-emerald-600" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-foreground">B&eacute;n&eacute;ficiaires</h3>
                  <p className="text-[11px] text-muted-foreground">{sortedAdvertisers.length} marque{sortedAdvertisers.length > 1 ? "s" : ""} identifi&eacute;e{sortedAdvertisers.length > 1 ? "s" : ""}</p>
                </div>
              </div>
              {hasMore && (
                <button
                  onClick={() => setShowAllPayers(v => !v)}
                  className="text-[11px] font-medium text-emerald-600 hover:text-emerald-700 transition-colors"
                >
                  {showAllPayers ? "Réduire" : `Voir tout (${sortedAdvertisers.length})`}
                </button>
              )}
            </div>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {visibleAdvertisers.map(([name, data]) => {
                const maxTotal = Math.max(...Array.from(stats.byAdvertiser.values()).map(v => v.total), 1);
                const pct = (data.total / maxTotal) * 100;
                return (
                  <button
                    key={name}
                    onClick={() => toggleFilter(filterAdvertisers, name, setFilterAdvertisers)}
                    className={`w-full text-left rounded-xl border p-3.5 transition-all hover:shadow-md ${
                      filterAdvertisers.has(name) ? "border-emerald-300 bg-emerald-50/50 shadow-sm" : "bg-card hover:bg-accent/30"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2.5 min-w-0">
                        {data.logo ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={data.logo} alt="" className="h-8 w-8 rounded-full object-cover border border-border shrink-0" />
                        ) : (
                          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-100 to-emerald-200 flex items-center justify-center shrink-0">
                            <Building2 className="h-4 w-4 text-emerald-600" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <span className="text-sm font-semibold truncate block">{name}</span>
                          <span className="shrink-0 inline-flex items-center text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                            Payeur
                          </span>
                        </div>
                      </div>
                      <span className="text-lg font-bold tabular-nums shrink-0 ml-2">{data.total}</span>
                    </div>
                    <div className="h-1 rounded-full bg-muted overflow-hidden mb-1.5">
                      <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground flex-wrap">
                      <span className="text-emerald-600 font-medium">{data.active} actives</span>
                      {data.spendMax > 0 && (
                        <span className="text-emerald-600 font-medium tabular-nums">
                          {formatNumber(data.spendMin)}&ndash;{formatNumber(data.spendMax)}&euro;
                        </span>
                      )}
                      {data.likes != null && data.likes > 0 && (
                        <span className="flex items-center gap-1">
                          <ThumbsUp className="h-3 w-3" />{formatNumber(data.likes)}
                        </span>
                      )}
                      {data.categories && data.categories.length > 0 && (
                        <span className="flex items-center gap-1">
                          <Tag className="h-3 w-3" />{data.categories.join(", ")}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        );
      })()}

      {/* ── Diffusion & Audience ────── */}
      <div className="rounded-2xl border bg-card/50 p-5 space-y-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-100">
            <Globe className="h-4.5 w-4.5 text-blue-600" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">Diffusion & Audience</h3>
            <p className="text-[11px] text-muted-foreground">Répartition par plateforme et concurrent</p>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* Platform reach per competitor with platform icons */}
          <div className="rounded-xl border bg-card p-4 space-y-3">
            <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Plateformes par concurrent</div>
            {Array.from(stats.competitorPlatforms.entries())
              .sort((a, b) => {
                const totalA = Array.from(a[1].values()).reduce((s, v) => s + v, 0);
                const totalB = Array.from(b[1].values()).reduce((s, v) => s + v, 0);
                return totalB - totalA;
              })
              .map(([competitor, platforms]) => (
                <div key={competitor} className="space-y-1.5">
                  <div className="text-xs font-semibold">{competitor}</div>
                  <div className="flex gap-1 flex-wrap">
                    {Array.from(platforms.entries())
                      .sort((a, b) => b[1] - a[1])
                      .map(([platform, count]) => {
                        const competitorTotal = stats.byCompetitor.get(competitor)?.total || 1;
                        const pctOfAds = Math.round((count / competitorTotal) * 100);
                        return (
                          <span key={platform} className={`inline-flex items-center gap-1.5 text-[10px] font-medium px-2.5 py-1 rounded-lg border ${PLATFORM_CONFIGS[platform]?.color || "bg-gray-100 text-gray-600 border-gray-200"}`}>
                            <PlatformIcon name={platform} className="h-3 w-3" />
                            {PLATFORM_CONFIGS[platform]?.label || platform.toLowerCase().replace("_", " ")}
                            <span className="font-bold tabular-nums">{pctOfAds}%</span>
                          </span>
                        );
                      })}
                  </div>
                </div>
              ))}
          </div>

          <div className="space-y-4 flex flex-col">
            {/* Key diffusion metrics */}
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-xl border bg-card p-3">
                <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Duree moyenne</div>
                <div className="text-xl font-bold mt-1 tabular-nums">{stats.avgDuration}<span className="text-sm font-normal text-muted-foreground ml-1">jours</span></div>
              </div>
              <div className="rounded-xl border bg-card p-3">
                <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Plateformes</div>
                <div className="text-xl font-bold mt-1 tabular-nums">{stats.byPlatform.size}<span className="text-sm font-normal text-muted-foreground ml-1">actives</span></div>
              </div>
              {stats.totalReach > 0 && (
                <div className="rounded-xl border bg-card p-3">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Personnes touch&eacute;es</div>
                  <div className="text-xl font-bold mt-1 tabular-nums text-blue-600">{formatNumber(stats.totalReach)}</div>
                </div>
              )}
              {stats.totalImpressions > 0 && (
                <div className="rounded-xl border bg-card p-3">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Impressions</div>
                  <div className="text-xl font-bold mt-1 tabular-nums text-violet-600">{formatNumber(stats.totalImpressions)}</div>
                </div>
              )}
              {stats.totalReach === 0 && (
                <div className="rounded-xl border bg-card p-3">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Concurrents</div>
                  <div className="text-xl font-bold mt-1 tabular-nums">{stats.byCompetitor.size}</div>
                </div>
              )}
              {stats.totalImpressions === 0 && (
                <div className="rounded-xl border bg-card p-3">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-widest">Formats</div>
                  <div className="text-xl font-bold mt-1 tabular-nums">{stats.byFormat.size}<span className="text-sm font-normal text-muted-foreground ml-1">types</span></div>
                </div>
              )}
            </div>

            {/* Platform total distribution with icons */}
            <div className="rounded-xl border bg-card p-4 space-y-2.5 flex-1">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Distribution globale</div>
              {Array.from(stats.byPlatform.entries())
                .sort((a, b) => b[1] - a[1])
                .map(([platform, count]) => {
                  const maxPlatform = Math.max(...Array.from(stats.byPlatform.values()), 1);
                  const pct = Math.round((count / maxPlatform) * 100);
                  const pctTotal = filteredAds.length > 0 ? Math.round((count / filteredAds.length) * 100) : 0;
                  return (
                    <div key={platform} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-xs font-medium">
                          <PlatformIcon name={platform} className={`h-3.5 w-3.5 ${PLATFORM_CONFIGS[platform]?.iconColor || "text-gray-500"}`} />
                          {PLATFORM_CONFIGS[platform]?.label || platform.toLowerCase().replace("_", " ")}
                        </span>
                        <span className="text-xs tabular-nums text-muted-foreground">{count} pubs ({pctTotal}%)</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-600" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
            </div>

            {/* Format breakdown */}
            <div className="rounded-xl border bg-card p-4 space-y-2.5">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Formats cr&eacute;atifs</div>
              {Array.from(stats.byFormat.entries())
                .sort((a, b) => b[1] - a[1])
                .map(([format, count]) => {
                  const maxFormat = Math.max(...Array.from(stats.byFormat.values() as Iterable<number>), 1);
                  const pct = Math.round(((count as number) / maxFormat) * 100);
                  const pctTotal = filteredAds.length > 0 ? Math.round(((count as number) / filteredAds.length) * 100) : 0;
                  return (
                    <div key={format} className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium capitalize">{(format as string).toLowerCase().replace(/_/g, " ")}</span>
                        <span className="text-xs tabular-nums text-muted-foreground">{count as number} ({pctTotal}%)</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-gradient-to-r from-violet-400 to-violet-600" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      </div>

      {/* ── Solutions Mobsuccess ──────── */}
      <MobsuccessRecommendations filteredAds={filteredAds} brandName={brandName} />

      {/* ── Ads Grid ─────────────────────────── */}
      {filteredAds.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-card/50 p-12 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50">
              <Megaphone className="h-7 w-7 text-violet-400" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-1">
            {activeFilters > 0 ? "Aucun résultat avec ces filtres" : "Aucune publicité enregistrée"}
          </h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            {activeFilters > 0
              ? "Essayez d'élargir vos critères de recherche."
              : "Cliquez sur Scanner tout pour chercher dans la Meta Ad Library."
            }
          </p>
          {activeFilters > 0 && (
            <Button variant="outline" size="sm" onClick={clearAllFilters} className="mt-4 gap-2">
              <X className="h-3.5 w-3.5" />Effacer les filtres
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100">
              <Eye className="h-4 w-4 text-violet-600" />
            </div>
            <h3 className="text-[13px] font-semibold text-foreground">
              {filteredAds.length} publicit&eacute;{filteredAds.length > 1 ? "s" : ""}
            </h3>
            {activeFilters > 0 && (
              <span className="text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                {activeFilters} filtre{activeFilters > 1 ? "s" : ""} actif{activeFilters > 1 ? "s" : ""}
              </span>
            )}
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {visibleAds.map((ad) => (
              <AdCard
                key={ad.ad_id}
                ad={ad}
                expanded={expandedAds.has(ad.ad_id)}
                onToggle={() => toggleExpand(ad.ad_id)}
                advertiserLogo={ad.page_name ? advertiserLogos.get(ad.page_name) : undefined}
                brandName={brandName}
              />
            ))}
          </div>
          {hasMoreAds && (
            <div className="flex justify-center pt-2">
              <Button variant="outline" size="sm" onClick={() => setVisibleCount(v => v + 12)} className="gap-2">
                <ChevronDown className="h-3.5 w-3.5" />
                Voir plus ({filteredAds.length - visibleCount} restantes)
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
