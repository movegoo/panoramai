"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  brandAPI,
  BrandProfileData,
  BrandSetupData,
  SectorData,
  CompetitorSuggestionData,
} from "@/lib/api";
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

  // Sync from parent when value changes externally (e.g. profile load)
  useEffect(() => {
    setRaw(value || "");
  }, [value]);

  const parsed = channel.parse(raw);
  const isUrl = raw.includes("://") || raw.includes("www.");
  const wasTransformed = isUrl && parsed !== raw && parsed !== "";

  function handleBlur() {
    setFocused(false);
    if (raw && parsed) {
      onChange(parsed);
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setRaw(v);
    // Auto-parse on paste (when value changes significantly)
    const p = channel.parse(v);
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
/* Main Page                                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */
export default function AccountPage() {
  const [profile, setProfile] = useState<BrandProfileData | null>(null);
  const [sectors, setSectors] = useState<SectorData[]>([]);
  const [suggestions, setSuggestions] = useState<CompetitorSuggestionData[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [isNewBrand, setIsNewBrand] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [addingCompetitor, setAddingCompetitor] = useState<string | null>(null);
  const [expandedSuggestion, setExpandedSuggestion] = useState<string | null>(null);

  const [form, setForm] = useState<BrandSetupData>({
    company_name: "",
    sector: "",
    website: "",
    instagram_username: "",
    tiktok_username: "",
    youtube_channel_id: "",
    playstore_app_id: "",
    appstore_app_id: "",
  });

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  async function loadData() {
    setLoading(true);
    try {
      const sectorsData = await brandAPI.getSectors();
      setSectors(sectorsData);

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
          playstore_app_id: profileData.playstore_app_id || "",
          appstore_app_id: profileData.appstore_app_id || "",
        });

        const suggestionsData = await brandAPI.getSuggestions();
        setSuggestions(suggestionsData);
      } catch {
        setIsNewBrand(true);
        setEditing(true);
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
    if (profile) {
      setForm({
        company_name: profile.company_name,
        sector: profile.sector,
        website: profile.website || "",
        instagram_username: profile.instagram_username || "",
        tiktok_username: profile.tiktok_username || "",
        youtube_channel_id: profile.youtube_channel_id || "",
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

  function updateForm(key: string, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
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
    <div className="space-y-6 max-w-4xl">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
          <Building2 className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            {isNewBrand ? "Bienvenue" : "Mon enseigne"}
          </h1>
          <p className="text-[13px] text-muted-foreground">
            {isNewBrand
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
                {isNewBrand ? "Creer mon enseigne" : "Mon enseigne"}
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
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4 mr-1" />
              Modifier
            </Button>
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
                <Input
                  id="website"
                  value={form.website}
                  onChange={(e) => updateForm("website", e.target.value)}
                  placeholder="https://www.auchan.fr"
                />
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
                  {isNewBrand ? "Creer mon compte" : "Sauvegarder"}
                </Button>
                {!isNewBrand && (
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
              {/* Info grid */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
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
      {/* Section 2 : Concurrents Suggeres                                  */}
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
                              {channelCount} canal{channelCount > 1 ? "x" : ""}
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
                          {!comp.website && !comp.instagram_username && !comp.tiktok_username &&
                           !comp.youtube_channel_id && !comp.playstore_app_id && !comp.appstore_app_id && (
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
