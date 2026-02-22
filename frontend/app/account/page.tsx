"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  brandAPI,
  BrandProfileData,
  BrandSetupData,
  BrandListItem,
  SectorData,
  CompetitorSuggestionData,
  setCurrentAdvertiserId,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  Building2,
  Globe,
  Instagram,
  Smartphone,
  Play,
  Youtube,
  Save,
  Pencil,
  X,
  Check,
  Plus,
  UserPlus,
  Hash,
  Loader2,
  Store,
  CheckCircle2,
  AlertCircle,
  Link2,
  Eye,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Sparkles,
  RefreshCw,
  Info,
  Plug,
  ShoppingCart,
  BarChart3,
  Mail,
  CreditCard,
  Star,
  Database,
  Megaphone,
  Lock,
  Clock,
  Wallet,
  MessageSquare,
  Package,
  MapPin,
  TrendingUp,
  ShieldCheck,
  Zap,
  Camera,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════════════ */
/* SVG Icons                                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */
function TikTokIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z" />
    </svg>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* URL Parsing - Extract IDs from URLs or raw values                         */
/* ═══════════════════════════════════════════════════════════════════════════ */
function parsePlayStoreInput(input: string): string {
  if (!input) return "";
  const trimmed = input.trim();
  // URL: https://play.google.com/store/apps/details?id=com.auchan.android
  try {
    const url = new URL(trimmed);
    if (url.hostname.includes("play.google.com")) {
      return url.searchParams.get("id") || trimmed;
    }
  } catch {}
  return trimmed;
}

function parseAppStoreInput(input: string): string {
  if (!input) return "";
  const trimmed = input.trim();
  // URL: https://apps.apple.com/fr/app/auchan/id393068659
  const match = trimmed.match(/\/id(\d+)/);
  if (match) return match[1];
  // Already a numeric ID
  if (/^\d+$/.test(trimmed)) return trimmed;
  return trimmed;
}

function parseInstagramInput(input: string): string {
  if (!input) return "";
  const trimmed = input.trim().replace(/^@/, "");
  // URL: https://www.instagram.com/auchan_france/
  try {
    const url = new URL(trimmed);
    if (url.hostname.includes("instagram.com")) {
      const path = url.pathname.replace(/^\//, "").replace(/\/$/, "");
      return path.split("/")[0] || trimmed;
    }
  } catch {}
  return trimmed;
}

function parseTikTokInput(input: string): string {
  if (!input) return "";
  const trimmed = input.trim().replace(/^@/, "");
  // URL: https://www.tiktok.com/@auchan
  try {
    const url = new URL(trimmed);
    if (url.hostname.includes("tiktok.com")) {
      const path = url.pathname.replace(/^\//, "").replace(/\/$/, "");
      return path.replace(/^@/, "").split("/")[0] || trimmed;
    }
  } catch {}
  return trimmed;
}

function parseYouTubeInput(input: string): string {
  if (!input) return "";
  const trimmed = input.trim();
  // URL: https://www.youtube.com/channel/UCxxxxxx or https://www.youtube.com/@handle
  try {
    const url = new URL(trimmed);
    if (url.hostname.includes("youtube.com")) {
      const path = url.pathname.replace(/^\//, "").replace(/\/$/, "");
      if (path.startsWith("channel/")) return path.replace("channel/", "");
      if (path.startsWith("@")) return path;
      if (path.startsWith("c/")) return path;
      return path || trimmed;
    }
  } catch {}
  return trimmed;
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* Channel definitions                                                       */
/* ═══════════════════════════════════════════════════════════════════════════ */
const CHANNELS = [
  {
    key: "instagram_username",
    label: "Instagram",
    icon: Instagram,
    color: "text-pink-500",
    bg: "bg-pink-50",
    border: "border-pink-200",
    placeholder: "@auchan_france ou https://instagram.com/auchan_france",
    hint: "Username ou URL du profil",
    parse: parseInstagramInput,
    formatDisplay: (v: string) => `@${v}`,
    profileUrl: (v: string) => `https://instagram.com/${v}`,
  },
  {
    key: "tiktok_username",
    label: "TikTok",
    icon: TikTokIcon,
    color: "text-slate-800",
    bg: "bg-slate-50",
    border: "border-slate-200",
    placeholder: "@auchan ou https://tiktok.com/@auchan",
    hint: "Username ou URL du profil",
    parse: parseTikTokInput,
    formatDisplay: (v: string) => `@${v}`,
    profileUrl: (v: string) => `https://tiktok.com/@${v}`,
  },
  {
    key: "youtube_channel_id",
    label: "YouTube",
    icon: Youtube,
    color: "text-red-500",
    bg: "bg-red-50",
    border: "border-red-200",
    placeholder: "UCxxxxxx ou https://youtube.com/@handle",
    hint: "Channel ID, @handle ou URL",
    parse: parseYouTubeInput,
    formatDisplay: (v: string) => v.startsWith("UC") ? v.slice(0, 12) + "..." : v,
    profileUrl: (v: string) => v.startsWith("UC") ? `https://youtube.com/channel/${v}` : `https://youtube.com/${v}`,
  },
  {
    key: "snapchat_entity_name",
    label: "Snapchat",
    icon: Hash,
    color: "text-yellow-500",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    placeholder: "Nom de l'entite sur Snapchat Ads",
    hint: "Nom d'annonceur Snapchat",
    parse: (v: string) => v.trim(),
    formatDisplay: (v: string) => v,
    profileUrl: (v: string) => `https://adsgallery.snap.com/`,
  },
  {
    key: "playstore_app_id",
    label: "Google Play",
    icon: Play,
    color: "text-green-600",
    bg: "bg-green-50",
    border: "border-green-200",
    placeholder: "com.auchan.android ou URL Play Store",
    hint: "App ID ou lien Play Store",
    parse: parsePlayStoreInput,
    formatDisplay: (v: string) => v,
    profileUrl: (v: string) => `https://play.google.com/store/apps/details?id=${v}`,
  },
  {
    key: "appstore_app_id",
    label: "App Store",
    icon: Smartphone,
    color: "text-sky-500",
    bg: "bg-sky-50",
    border: "border-sky-200",
    placeholder: "393068659 ou URL App Store",
    hint: "ID numerique ou lien App Store",
    parse: parseAppStoreInput,
    formatDisplay: (v: string) => `id${v}`,
    profileUrl: (v: string) => `https://apps.apple.com/app/id${v}`,
  },
] as const;

type ChannelKey = (typeof CHANNELS)[number]["key"];

/* ═══════════════════════════════════════════════════════════════════════════ */
/* Smart Input Component - Accepts URLs & shows extracted ID                 */
/* ═══════════════════════════════════════════════════════════════════════════ */
function SmartChannelInput({
  channel,
  value,
  onChange,
}: {
  channel: (typeof CHANNELS)[number];
  value: string;
  onChange: (parsed: string) => void;
}) {
  const [raw, setRaw] = useState(value || "");
  const [focused, setFocused] = useState(false);
  // Track the last value WE sent to parent, so we can distinguish
  // our own updates from external ones (profile load, cancel, save)
  const lastSentValue = useRef(value || "");

  useEffect(() => {
    // Only sync when parent value changed for an external reason
    if (value !== lastSentValue.current) {
      lastSentValue.current = value || "";
      setRaw(value || "");
    }
  }, [value]);

  const parsed = channel.parse(raw);
  const isUrl = raw.includes("://") || raw.includes("www.");
  const wasTransformed = isUrl && parsed !== raw && parsed !== "";

  function handleBlur() {
    setFocused(false);
    if (raw && parsed) {
      lastSentValue.current = parsed;
      onChange(parsed);
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setRaw(v);
    const p = channel.parse(v);
    lastSentValue.current = p;
    onChange(p);
  }

  const Icon = channel.icon;

  return (
    <div className="space-y-1">
      <Label htmlFor={channel.key} className="text-xs flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${channel.color}`} />
        {channel.label}
      </Label>
      <div className="relative">
        <Input
          id={channel.key}
          value={raw}
          onChange={handleChange}
          onFocus={() => setFocused(true)}
          onBlur={handleBlur}
          placeholder={channel.placeholder}
          className={`h-9 text-sm pr-8 ${
            wasTransformed && !focused
              ? `${channel.border} border-2`
              : ""
          }`}
        />
        {parsed && !focused && (
          <a
            href={channel.profileUrl(parsed)}
            target="_blank"
            rel="noopener noreferrer"
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            title="Ouvrir"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>
      {wasTransformed && (
        <p className="flex items-center gap-1 text-[11px] text-emerald-600">
          <Check className="h-3 w-3" />
          ID extrait : <span className="font-mono font-medium">{parsed}</span>
        </p>
      )}
      {!parsed && !focused && (
        <p className="text-[11px] text-muted-foreground">{channel.hint}</p>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* Connectors Section                                                        */
/* ═══════════════════════════════════════════════════════════════════════════ */

interface Connector {
  id: string;
  name: string;
  description: string;
  icon: any;
  color: string;
  bg: string;
  border: string;
  status: "connected" | "available" | "coming_soon";
  category: "analytics" | "ads" | "crm" | "ecommerce" | "data" | "reviews";
  badge?: string;
  syncLabel?: string;
}

const CONNECTORS: Connector[] = [
  // --- Connected (demo) ---
  {
    id: "ga4", name: "Google Analytics 4", description: "Trafic, conversions, audiences",
    icon: BarChart3, color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200",
    status: "connected", category: "analytics", badge: "12.4k sessions/j", syncLabel: "Synchro il y a 2h",
  },
  {
    id: "meta_business", name: "Meta Business Suite", description: "Facebook & Instagram Ads, audiences",
    icon: Megaphone, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200",
    status: "connected", category: "ads", badge: "3 campagnes actives", syncLabel: "Synchro il y a 1h",
  },
  {
    id: "gmb", name: "Google Business Profile", description: "Fiches etablissements, avis, visibilite locale",
    icon: MapPin, color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200",
    status: "connected", category: "reviews", badge: "47 fiches", syncLabel: "Synchro il y a 4h",
  },
  {
    id: "loyalty", name: "Programme fidelite", description: "Base clients, segmentation, panier moyen",
    icon: Wallet, color: "text-violet-600", bg: "bg-violet-50", border: "border-violet-200",
    status: "connected", category: "crm", badge: "2.3M membres", syncLabel: "Synchro quotidienne",
  },
  // --- Available ---
  {
    id: "google_ads", name: "Google Ads", description: "Campagnes Search, Display, Shopping",
    icon: TrendingUp, color: "text-blue-500", bg: "bg-blue-50", border: "border-blue-200",
    status: "available", category: "ads",
  },
  {
    id: "shopify", name: "Shopify", description: "Commandes, produits, inventaire e-commerce",
    icon: ShoppingCart, color: "text-green-600", bg: "bg-green-50", border: "border-green-200",
    status: "available", category: "ecommerce",
  },
  {
    id: "salesforce", name: "Salesforce CRM", description: "Contacts, pipeline, opportunites",
    icon: Database, color: "text-sky-600", bg: "bg-sky-50", border: "border-sky-200",
    status: "available", category: "crm",
  },
  {
    id: "hubspot", name: "HubSpot", description: "CRM, marketing automation, leads",
    icon: MessageSquare, color: "text-orange-500", bg: "bg-orange-50", border: "border-orange-200",
    status: "available", category: "crm",
  },
  {
    id: "mailchimp", name: "Mailchimp", description: "Campagnes email, taux d'ouverture, audiences",
    icon: Mail, color: "text-yellow-600", bg: "bg-yellow-50", border: "border-yellow-200",
    status: "available", category: "ads",
  },
  {
    id: "pos_caisse", name: "Caisse / POS", description: "Donnees de vente en magasin, ticket moyen",
    icon: CreditCard, color: "text-slate-600", bg: "bg-slate-50", border: "border-slate-200",
    status: "available", category: "data",
  },
  {
    id: "trustpilot", name: "Trustpilot", description: "Avis clients, NPS, reputation en ligne",
    icon: Star, color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200",
    status: "available", category: "reviews",
  },
  {
    id: "erp_sap", name: "SAP / ERP", description: "Stock, approvisionnement, logistique",
    icon: Package, color: "text-indigo-600", bg: "bg-indigo-50", border: "border-indigo-200",
    status: "available", category: "data",
  },
  {
    id: "gsc", name: "Search Console", description: "Impressions, clics, positions SEO",
    icon: Globe, color: "text-violet-500", bg: "bg-violet-50", border: "border-violet-200",
    status: "available", category: "analytics",
  },
  // --- Coming soon ---
  {
    id: "bigquery", name: "BigQuery / Snowflake", description: "Data warehouse, requetes SQL directes",
    icon: Database, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200",
    status: "coming_soon", category: "data",
  },
  {
    id: "tiktok_ads", name: "TikTok Ads", description: "Campagnes, audiences, conversions TikTok",
    icon: Zap, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200",
    status: "coming_soon", category: "ads",
  },
  {
    id: "criteo", name: "Criteo", description: "Retargeting, retail media, ROAS",
    icon: ShieldCheck, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200",
    status: "coming_soon", category: "ads",
  },
];

const CATEGORY_LABELS: Record<string, string> = {
  analytics: "Analytics",
  ads: "Publicite",
  crm: "CRM & Fidelite",
  ecommerce: "E-commerce",
  data: "Data & ERP",
  reviews: "Avis & Reputation",
};

function ConnectorsSection() {
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  const connectedCount = CONNECTORS.filter(c => c.status === "connected").length;
  const filtered = filter === "all"
    ? CONNECTORS
    : CONNECTORS.filter(c => c.category === filter);

  const categories = Array.from(new Set(CONNECTORS.map(c => c.category)));

  function handleConnect(id: string) {
    setConnectingId(id);
    setTimeout(() => setConnectingId(null), 2000);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-100 to-violet-100">
              <Plug className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <CardTitle className="text-lg">Connecteurs & Integrations</CardTitle>
              <p className="text-sm text-muted-foreground">
                {connectedCount} connecte{connectedCount > 1 ? "s" : ""} sur {CONNECTORS.length} disponibles
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:flex items-center gap-1.5 text-[11px] text-emerald-600 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full font-medium">
              <Zap className="h-3 w-3" />
              Inclus dans votre plan
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Category filter */}
        <div className="flex flex-wrap gap-1.5">
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
              filter === "all"
                ? "bg-indigo-100 text-indigo-700 border border-indigo-200"
                : "bg-gray-50 text-gray-600 border border-transparent hover:bg-gray-100"
            }`}
          >
            Tous ({CONNECTORS.length})
          </button>
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setFilter(cat)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                filter === cat
                  ? "bg-indigo-100 text-indigo-700 border border-indigo-200"
                  : "bg-gray-50 text-gray-600 border border-transparent hover:bg-gray-100"
              }`}
            >
              {CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>

        {/* Connector grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {filtered.map(connector => {
            const Icon = connector.icon;
            const isConnecting = connectingId === connector.id;
            return (
              <div
                key={connector.id}
                className={`rounded-xl border p-4 transition-all ${
                  connector.status === "connected"
                    ? `${connector.bg} ${connector.border} border-2`
                    : connector.status === "coming_soon"
                    ? "bg-gray-50/50 border-dashed border-gray-200 opacity-75"
                    : "bg-white border-gray-200 hover:border-gray-300 hover:shadow-sm"
                }`}
              >
                {/* Icon + Info + Status badge */}
                <div className="flex items-start gap-3">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-lg shrink-0 ${
                    connector.status === "connected" ? "bg-white shadow-sm" : connector.bg
                  }`}>
                    <Icon className={`h-5 w-5 ${connector.color}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className={`text-sm font-semibold ${
                        connector.status === "coming_soon" ? "text-gray-500" : "text-foreground"
                      }`}>
                        {connector.name}
                      </p>
                      {connector.status === "connected" && (
                        <span className="flex items-center gap-1 rounded-full bg-emerald-100 border border-emerald-200 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 shrink-0">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                          Connecte
                        </span>
                      )}
                      {connector.status === "coming_soon" && (
                        <span className="flex items-center gap-1 rounded-full bg-gray-100 border border-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-500 shrink-0">
                          <Clock className="h-2.5 w-2.5" />
                          Bientot
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                      {connector.description}
                    </p>
                  </div>
                </div>

                {/* Connected: show badge + sync info */}
                {connector.status === "connected" && (
                  <div className="mt-3 pt-3 border-t border-current/10 space-y-1.5">
                    {connector.badge && (
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-bold ${connector.color}`}>{connector.badge}</span>
                      </div>
                    )}
                    {connector.syncLabel && (
                      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                        <RefreshCw className="h-2.5 w-2.5" />
                        {connector.syncLabel}
                      </div>
                    )}
                  </div>
                )}

                {/* Available: connect button */}
                {connector.status === "available" && (
                  <div className="mt-3">
                    <button
                      onClick={() => handleConnect(connector.id)}
                      disabled={isConnecting}
                      className="w-full flex items-center justify-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all disabled:opacity-50"
                    >
                      {isConnecting ? (
                        <>
                          <Loader2 className="h-3 w-3 animate-spin" />
                          Connexion...
                        </>
                      ) : (
                        <>
                          <Plug className="h-3 w-3" />
                          Connecter
                        </>
                      )}
                    </button>
                  </div>
                )}

                {/* Coming soon: locked */}
                {connector.status === "coming_soon" && (
                  <div className="mt-3">
                    <div className="w-full flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-400">
                      <Lock className="h-3 w-3" />
                      Disponible prochainement
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer info */}
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground bg-gradient-to-r from-indigo-50 to-violet-50 rounded-lg px-4 py-3 border border-indigo-100">
          <Info className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
          <span>
            Les connecteurs enrichissent automatiquement vos analyses concurrentielles avec vos donnees first-party.
            Donnees chiffrees, synchronisees et securisees.
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* Main Page                                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */
export default function AccountPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, refresh: refreshAuth, switchAdvertiser } = useAuth();
  const isNewMode = searchParams.get("new") === "1";

  const [profile, setProfile] = useState<BrandProfileData | null>(null);
  const [allBrands, setAllBrands] = useState<BrandListItem[]>([]);
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [suggestions, setSuggestions] = useState<CompetitorSuggestionData[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [isNewBrand, setIsNewBrand] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [addingCompetitor, setAddingCompetitor] = useState<string | null>(null);
  const [expandedSuggestion, setExpandedSuggestion] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [detectingSocials, setDetectingSocials] = useState(false);
  const [detectedCount, setDetectedCount] = useState(0);

  const [form, setForm] = useState<BrandSetupData>({
    company_name: "",
    sector: "",
    website: "",
    instagram_username: "",
    tiktok_username: "",
    youtube_channel_id: "",
    snapchat_entity_name: "",
    playstore_app_id: "",
    appstore_app_id: "",
  });

  const skipNextLoad = useRef(false);

  useEffect(() => {
    if (skipNextLoad.current) {
      skipNextLoad.current = false;
      return;
    }
    loadData();
  }, [isNewMode]);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  async function loadData() {
    setLoading(true);
    try {
      const [sectorsData, brands] = await Promise.all([
        brandAPI.getSectors(),
        brandAPI.list().catch(() => []),
      ]);
      setSectors(sectorsData);
      setAllBrands(brands);

      // If ?new=1, show creation form directly
      if (isNewMode) {
        setIsNewBrand(true);
        setEditing(true);
        setProfile(null);
        setForm({
          company_name: "", sector: "", website: "",
          instagram_username: "", tiktok_username: "", youtube_channel_id: "",
          snapchat_entity_name: "", playstore_app_id: "", appstore_app_id: "",
        });
      } else {
        try {
          const profileData = await brandAPI.getProfile();
          setProfile(profileData);
          setForm({
            company_name: profileData.company_name,
            sector: profileData.sector,
            website: profileData.website || "",
            instagram_username: profileData.instagram_username || "",
            tiktok_username: profileData.tiktok_username || "",
            youtube_channel_id: profileData.youtube_channel_id || "",
            snapchat_entity_name: profileData.snapchat_entity_name || "",
            playstore_app_id: profileData.playstore_app_id || "",
            appstore_app_id: profileData.appstore_app_id || "",
          });

          const suggestionsData = await brandAPI.getSuggestions();
          setSuggestions(suggestionsData);
        } catch {
          setIsNewBrand(true);
          setEditing(true);
        }
      }
    } catch (err) {
      console.error("Failed to load account data:", err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!form.company_name || !form.sector) return;

    setSaving(true);
    try {
      if (isNewBrand) {
        const result = await brandAPI.setup(form);
        setProfile(result.brand);
        setSuggestions(result.suggested_competitors);
        setIsNewBrand(false);
        setToast({ type: "success", text: result.message });
        // Switch to the newly created advertiser
        setCurrentAdvertiserId(result.brand.id);
        // Refresh the auth context to pick up the new advertiser list
        await refreshAuth();
        // Refresh local brand list
        const brands = await brandAPI.list().catch(() => []);
        setAllBrands(brands);
        // Remove ?new=1 from URL without re-fetching (we already have the data)
        skipNextLoad.current = true;
        router.replace("/account");
      } else {
        const updated = await brandAPI.updateProfile(form);
        setProfile(updated);
        const suggestionsData = await brandAPI.getSuggestions();
        setSuggestions(suggestionsData);
        setToast({ type: "success", text: "Profil mis a jour avec succes" });
      }
      setEditing(false);
    } catch (err: any) {
      setToast({ type: "error", text: err.message || "Erreur lors de la sauvegarde" });
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    // If we were in new brand mode from ?new=1, go back to normal account view
    if (isNewMode || (isNewBrand && allBrands.length > 0)) {
      setIsNewBrand(false);
      setEditing(false);
      router.replace("/account");
      // Reload current brand profile
      loadData();
      return;
    }
    if (profile) {
      setForm({
        company_name: profile.company_name,
        sector: profile.sector,
        website: profile.website || "",
        instagram_username: profile.instagram_username || "",
        tiktok_username: profile.tiktok_username || "",
        youtube_channel_id: profile.youtube_channel_id || "",
        snapchat_entity_name: profile.snapchat_entity_name || "",
        playstore_app_id: profile.playstore_app_id || "",
        appstore_app_id: profile.appstore_app_id || "",
      });
    }
    setEditing(false);
  }

  async function handleAddCompetitor(name: string) {
    setAddingCompetitor(name);
    try {
      await brandAPI.addSuggestions([name]);
      setSuggestions((prev) =>
        prev.map((s) => (s.name === name ? { ...s, already_tracked: true } : s))
      );
      if (profile) {
        setProfile({ ...profile, competitors_tracked: profile.competitors_tracked + 1 });
      }
      setToast({ type: "success", text: `${name} ajoute aux concurrents suivis` });
    } catch (err: any) {
      setToast({ type: "error", text: err.message || "Erreur" });
    } finally {
      setAddingCompetitor(null);
    }
  }

  async function handleAddAll() {
    const toAdd = suggestions.filter((s) => !s.already_tracked).map((s) => s.name);
    if (toAdd.length === 0) return;
    setAddingCompetitor("__all__");
    try {
      const result = await brandAPI.addSuggestions(toAdd);
      setSuggestions((prev) =>
        prev.map((s) => (toAdd.includes(s.name) ? { ...s, already_tracked: true } : s))
      );
      if (profile) {
        setProfile({ ...profile, competitors_tracked: profile.competitors_tracked + result.added.length });
      }
      setToast({ type: "success", text: `${result.added.length} concurrents ajoutes` });
    } catch (err: any) {
      setToast({ type: "error", text: err.message || "Erreur" });
    } finally {
      setAddingCompetitor(null);
    }
  }

  async function handleSync() {
    setSyncing(true);
    try {
      const result = await brandAPI.sync();
      setToast({ type: "success", text: result.message });
    } catch (err: any) {
      setToast({ type: "error", text: err.message || "Erreur lors de la synchronisation" });
    } finally {
      setSyncing(false);
    }
  }

  function updateForm(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleWebsiteBlur() {
    const website = form.website?.trim();
    if (!website || !form.company_name) return;
    try {
      new URL(website);
    } catch {
      return;
    }
    setDetectingSocials(true);
    setDetectedCount(0);
    try {
      const result = await brandAPI.suggestSocials(form.company_name, website);
      if (result.detected > 0) {
        let filled = 0;
        setForm((prev) => {
          const updated = { ...prev };
          for (const [key, value] of Object.entries(result.suggestions)) {
            if (value && !prev[key as keyof BrandSetupData]) {
              (updated as any)[key] = value;
              filled++;
            }
          }
          return updated;
        });
        setDetectedCount(filled);
      }
    } catch {
      // Silently ignore - this is a best-effort feature
    } finally {
      setDetectingSocials(false);
    }
  }

  /* ─── Loading ─── */
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement du profil...</span>
        </div>
      </div>
    );
  }

  const trackedCount = suggestions.filter((s) => s.already_tracked).length;
  const remainingCount = suggestions.filter((s) => !s.already_tracked).length;

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
          <Building2 className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            {isNewBrand && allBrands.length > 0 ? "Nouvelle enseigne" : isNewBrand ? "Bienvenue" : "Mon enseigne"}
          </h1>
          <p className="text-[13px] text-muted-foreground">
            {isNewBrand && allBrands.length > 0
              ? "Ajoutez une nouvelle enseigne à votre compte"
              : isNewBrand
              ? "Configurez votre marque pour démarrer la veille concurrentielle"
              : "Gérez votre profil et vos concurrents"}
          </p>
        </div>
      </div>

      {/* ── Toast ── */}
      {toast && (
        <div
          className={`flex items-center gap-2 rounded-lg border px-4 py-3 text-sm animate-in fade-in slide-in-from-top-2 ${
            toast.type === "success"
              ? "border-green-200 bg-green-50 text-green-800"
              : "border-red-200 bg-red-50 text-red-800"
          }`}
        >
          {toast.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <AlertCircle className="h-4 w-4 shrink-0" />
          )}
          {toast.text}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Section 0 : Mes enseignes (multi-advertiser switcher)             */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {allBrands.length > 1 && !isNewBrand && (
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Mes enseignes</p>
              <Button variant="ghost" size="sm" className="h-7 text-xs text-violet-600" onClick={() => router.push("/account?new=1")}>
                <Plus className="h-3.5 w-3.5 mr-1" />
                Ajouter
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {allBrands.map((b) => {
                const isCurrent = b.id === profile?.id;
                return (
                  <button
                    key={b.id}
                    onClick={() => {
                      if (!isCurrent) switchAdvertiser(b.id);
                    }}
                    className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-all ${
                      isCurrent
                        ? "bg-violet-50 border-violet-300 text-violet-700 font-semibold"
                        : "bg-white border-gray-200 text-gray-700 hover:border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    {b.logo_url ? (
                      <img src={b.logo_url} alt="" className="h-6 w-6 rounded-full object-contain" />
                    ) : (
                      <div className="h-6 w-6 rounded-full bg-gradient-to-br from-violet-100 to-indigo-100 flex items-center justify-center text-[10px] font-bold text-violet-700">
                        {b.company_name.charAt(0)}
                      </div>
                    )}
                    {b.company_name}
                    {isCurrent && <Check className="h-3.5 w-3.5 text-violet-600" />}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Section 1 : Profil                                                */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-violet-100">
              <Building2 className="h-5 w-5 text-violet-600" />
            </div>
            <div>
              <CardTitle className="text-lg">
                {isNewBrand && allBrands.length > 0 ? "Nouvelle enseigne" : isNewBrand ? "Creer mon enseigne" : "Mon enseigne"}
              </CardTitle>
              {profile && !editing && (
                <p className="text-sm text-muted-foreground">
                  {profile.sector_label} &middot; {profile.channels_configured} canaux &middot;{" "}
                  {profile.competitors_tracked} concurrents
                </p>
              )}
            </div>
          </div>
          {profile && !editing && (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSync}
                disabled={syncing}
                title="Relancer la collecte de données sur tous les canaux"
              >
                <RefreshCw className={`h-4 w-4 mr-1 ${syncing ? "animate-spin" : ""}`} />
                {syncing ? "Synchro..." : "Synchroniser"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                <Pencil className="h-4 w-4 mr-1" />
                Modifier
              </Button>
            </div>
          )}
        </CardHeader>

        <CardContent>
          {editing ? (
            /* ── Form ── */
            <form onSubmit={handleSave} className="space-y-6">
              {/* Basic info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="company_name">
                    <Building2 className="h-3.5 w-3.5 inline mr-1" />
                    Nom de l&apos;enseigne *
                  </Label>
                  <Input
                    id="company_name"
                    value={form.company_name}
                    onChange={(e) => updateForm("company_name", e.target.value)}
                    placeholder="ex: Auchan"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sector">
                    <Store className="h-3.5 w-3.5 inline mr-1" />
                    Secteur / Verticale *
                  </Label>
                  <select
                    id="sector"
                    value={form.sector}
                    onChange={(e) => updateForm("sector", e.target.value)}
                    required
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="">Choisir un secteur...</option>
                    {sectors.map((s) => (
                      <option key={s.code} value={s.code}>
                        {s.name} ({s.competitors_count} concurrents)
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="website">
                  <Globe className="h-3.5 w-3.5 inline mr-1" />
                  Site web
                </Label>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Input
                      id="website"
                      value={form.website}
                      onChange={(e) => updateForm("website", e.target.value)}
                      onBlur={handleWebsiteBlur}
                      placeholder="https://www.auchan.fr"
                      className={detectingSocials ? "pr-10" : ""}
                    />
                    {detectingSocials && (
                      <div className="absolute right-3 top-1/2 -translate-y-1/2">
                        <Loader2 className="h-4 w-4 animate-spin text-violet-500" />
                      </div>
                    )}
                  </div>
                  {form.website && !detectingSocials && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-10 shrink-0 text-violet-600 border-violet-200 hover:bg-violet-50"
                      onClick={handleWebsiteBlur}
                    >
                      <Sparkles className="h-3.5 w-3.5 mr-1" />
                      Detecter
                    </Button>
                  )}
                </div>
                {detectingSocials && (
                  <p className="flex items-center gap-1.5 text-[11px] text-violet-600">
                    <Sparkles className="h-3 w-3" />
                    Detection des reseaux sociaux en cours...
                  </p>
                )}
                {!detectingSocials && detectedCount > 0 && (
                  <p className="flex items-center gap-1.5 text-[11px] text-emerald-600">
                    <Sparkles className="h-3 w-3" />
                    {detectedCount} cana{detectedCount > 1 ? "ux" : "l"} detecte{detectedCount > 1 ? "s" : ""} automatiquement
                  </p>
                )}
              </div>

              {/* Channels with smart inputs */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Link2 className="h-4 w-4 text-muted-foreground" />
                  <h3 className="text-sm font-medium">Identifiants des canaux</h3>
                  <span className="text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                    Collez un lien ou entrez l&apos;ID directement
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {CHANNELS.map((ch) => (
                    <SmartChannelInput
                      key={ch.key}
                      channel={ch}
                      value={form[ch.key as ChannelKey] || ""}
                      onChange={(v) => updateForm(ch.key, v)}
                    />
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-3 pt-2">
                <Button type="submit" disabled={saving}>
                  {saving ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4 mr-1" />
                  )}
                  {isNewBrand ? "Creer l'enseigne" : "Sauvegarder"}
                </Button>
                {(!isNewBrand || allBrands.length > 0) && (
                  <Button type="button" variant="outline" onClick={handleCancel}>
                    <X className="h-4 w-4 mr-1" />
                    Annuler
                  </Button>
                )}
              </div>
            </form>
          ) : profile ? (
            /* ── Profile display ── */
            <div className="space-y-4">
              {/* Logo + Info */}
              <div className="flex items-start gap-5">
                <div className="relative group">
                  {profile.logo_url ? (
                    <img src={profile.logo_url} alt={profile.company_name} className="h-16 w-16 rounded-xl object-contain bg-white border border-border shadow-sm" />
                  ) : (
                    <div className="h-16 w-16 rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 flex items-center justify-center text-xl font-bold text-violet-700 border border-violet-200/50">
                      {profile.company_name.charAt(0)}
                    </div>
                  )}
                  <label className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer">
                    <Camera className="h-5 w-5 text-white" />
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        try {
                          const res = await brandAPI.uploadLogo(file);
                          setProfile((prev) => prev ? { ...prev, logo_url: res.logo_url } : prev);
                          refreshAuth();
                        } catch (err: any) {
                          alert(err.message || "Erreur lors de l'upload");
                        }
                      }}
                    />
                  </label>
                </div>
                <div className="flex-1">
              {/* Info grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">Nom</p>
                  <p className="font-semibold">{profile.company_name}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Secteur</p>
                  <p className="font-semibold">{profile.sector_label}</p>
                </div>
                {profile.website && (
                  <div>
                    <p className="text-xs text-muted-foreground">Site web</p>
                    <a
                      href={profile.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:underline flex items-center gap-1"
                    >
                      {profile.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                )}
              </div>
                </div>{/* end flex-1 */}
              </div>{/* end flex row */}

              {/* Channels badges */}
              <div>
                <p className="text-xs text-muted-foreground mb-2">Canaux configures</p>
                <div className="flex flex-wrap gap-2">
                  {CHANNELS.map((ch) => {
                    const value = profile[ch.key as keyof BrandProfileData] as string | undefined;
                    const Icon = ch.icon;
                    const active = !!value;
                    return (
                      <div key={ch.key}>
                        {active ? (
                          <a
                            href={ch.profileUrl(value!)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border transition-colors hover:opacity-80 ${ch.bg} ${ch.color} border-transparent`}
                          >
                            <Icon className="h-3.5 w-3.5" />
                            {ch.formatDisplay(value!)}
                            <ExternalLink className="h-2.5 w-2.5 opacity-60" />
                          </a>
                        ) : (
                          <div className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border bg-gray-50 text-gray-400 border-gray-200">
                            <Icon className="h-3.5 w-3.5" />
                            {ch.label}
                            <X className="h-3 w-3 ml-0.5 opacity-50" />
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3 pt-2">
                <div className="rounded-lg border bg-violet-50/50 p-3 text-center">
                  <p className="text-2xl font-bold text-violet-600">
                    {profile.channels_configured}
                  </p>
                  <p className="text-xs text-muted-foreground">Canaux</p>
                </div>
                <div className="rounded-lg border bg-emerald-50/50 p-3 text-center">
                  <p className="text-2xl font-bold text-emerald-600">
                    {profile.competitors_tracked}
                  </p>
                  <p className="text-xs text-muted-foreground">Concurrents</p>
                </div>
                <div className="rounded-lg border bg-amber-50/50 p-3 text-center">
                  <p className="text-2xl font-bold text-amber-600">
                    {sectors.find((s) => s.code === profile.sector)?.competitors_count || 0}
                  </p>
                  <p className="text-xs text-muted-foreground">Dispo. secteur</p>
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Section 2 : Connecteurs & Integrations                            */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {!isNewBrand && profile && (
        <ConnectorsSection />
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Section 3 : Concurrents Suggeres                                  */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {!isNewBrand && suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100">
                  <UserPlus className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">Concurrents suggeres</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {trackedCount}/{suggestions.length} du secteur{" "}
                    {profile?.sector_label} suivis
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-24 rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all"
                      style={{
                        width: `${suggestions.length > 0 ? (trackedCount / suggestions.length) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground font-medium">
                    {suggestions.length > 0
                      ? Math.round((trackedCount / suggestions.length) * 100)
                      : 0}%
                  </span>
                </div>
                {remainingCount > 0 && (
                  <Button
                    size="sm"
                    variant="default"
                    className="h-8"
                    disabled={addingCompetitor === "__all__"}
                    onClick={handleAddAll}
                  >
                    {addingCompetitor === "__all__" ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5 mr-1" />
                    )}
                    Tout ajouter ({remainingCount})
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {suggestions.map((comp) => {
                const isExpanded = expandedSuggestion === comp.name;
                const channelCount = [
                  comp.instagram_username,
                  comp.tiktok_username,
                  comp.youtube_channel_id,
                  comp.playstore_app_id,
                  comp.appstore_app_id,
                ].filter(Boolean).length;

                return (
                  <div
                    key={comp.name}
                    className={`rounded-lg border transition-all ${
                      comp.already_tracked
                        ? "bg-emerald-50/50 border-emerald-200"
                        : "hover:bg-muted/30"
                    }`}
                  >
                    {/* Main row */}
                    <div className="flex items-center justify-between p-3">
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div
                          className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold shrink-0 ${
                            comp.already_tracked
                              ? "bg-emerald-100 text-emerald-700"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {comp.name.charAt(0)}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-sm">{comp.name}</p>
                            <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                              {channelCount} cana{channelCount > 1 ? "ux" : "l"}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            {comp.instagram_username && (
                              <span className="flex items-center gap-0.5 text-[11px] text-pink-500">
                                <Instagram className="h-3 w-3" />
                                @{comp.instagram_username}
                              </span>
                            )}
                            {comp.tiktok_username && (
                              <span className="flex items-center gap-0.5 text-[11px] text-slate-600">
                                <TikTokIcon className="h-3 w-3" />
                                @{comp.tiktok_username}
                              </span>
                            )}
                            {!comp.instagram_username && !comp.tiktok_username && comp.website && (
                              <span className="text-[11px] text-muted-foreground">
                                {comp.website.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "")}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {/* Expand button to see all IDs */}
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-8 w-8 p-0"
                          onClick={() => setExpandedSuggestion(isExpanded ? null : comp.name)}
                          title="Voir les identifiants"
                        >
                          {isExpanded ? (
                            <ChevronUp className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>

                        {comp.already_tracked ? (
                          <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-medium text-emerald-700">
                            <Check className="h-3 w-3" />
                            Suivi
                          </span>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8"
                            disabled={addingCompetitor === comp.name}
                            onClick={() => handleAddCompetitor(comp.name)}
                          >
                            {addingCompetitor === comp.name ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <>
                                <Plus className="h-3.5 w-3.5 mr-1" />
                                Ajouter
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>

                    {/* Expanded detail: all channel IDs */}
                    {isExpanded && (
                      <div className="px-3 pb-3 pt-0">
                        <div className="rounded-md bg-muted/50 p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {comp.website && (
                            <div className="flex items-center gap-2 text-xs">
                              <Globe className="h-3.5 w-3.5 text-blue-500 shrink-0" />
                              <a href={comp.website} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">
                                {comp.website.replace(/^https?:\/\//, "")}
                              </a>
                            </div>
                          )}
                          {comp.instagram_username && (
                            <div className="flex items-center gap-2 text-xs">
                              <Instagram className="h-3.5 w-3.5 text-pink-500 shrink-0" />
                              <span className="font-mono">@{comp.instagram_username}</span>
                            </div>
                          )}
                          {comp.tiktok_username && (
                            <div className="flex items-center gap-2 text-xs">
                              <TikTokIcon className="h-3.5 w-3.5 text-slate-700 shrink-0" />
                              <span className="font-mono">@{comp.tiktok_username}</span>
                            </div>
                          )}
                          {comp.youtube_channel_id && (
                            <div className="flex items-center gap-2 text-xs">
                              <Youtube className="h-3.5 w-3.5 text-red-500 shrink-0" />
                              <span className="font-mono truncate">{comp.youtube_channel_id}</span>
                            </div>
                          )}
                          {comp.playstore_app_id && (
                            <div className="flex items-center gap-2 text-xs">
                              <Play className="h-3.5 w-3.5 text-green-600 shrink-0" />
                              <a
                                href={`https://play.google.com/store/apps/details?id=${comp.playstore_app_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-mono text-blue-600 hover:underline truncate"
                              >
                                {comp.playstore_app_id}
                              </a>
                            </div>
                          )}
                          {comp.appstore_app_id && (
                            <div className="flex items-center gap-2 text-xs">
                              <Smartphone className="h-3.5 w-3.5 text-sky-500 shrink-0" />
                              <a
                                href={`https://apps.apple.com/app/id${comp.appstore_app_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="font-mono text-blue-600 hover:underline"
                              >
                                id{comp.appstore_app_id}
                              </a>
                            </div>
                          )}
                          {comp.snapchat_entity_name && (
                            <div className="flex items-center gap-2 text-xs">
                              <span className="text-yellow-500 shrink-0 text-sm">👻</span>
                              <span className="font-mono text-muted-foreground">{comp.snapchat_entity_name}</span>
                            </div>
                          )}
                          {!comp.website && !comp.instagram_username && !comp.tiktok_username &&
                           !comp.youtube_channel_id && !comp.playstore_app_id && !comp.appstore_app_id &&
                           !comp.snapchat_entity_name && (
                            <p className="text-xs text-muted-foreground col-span-2">Aucun identifiant pre-configure</p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
