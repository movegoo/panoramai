"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { competitorsAPI, enrichAPI, Competitor, CompetitorCreate, API_BASE, FreshnessData } from "@/lib/api";
import { FreshnessBadge } from "@/components/freshness-badge";
import { formatDate } from "@/lib/utils";
import {
  Plus,
  Pencil,
  Trash2,
  ExternalLink,
  Users,
  Globe,
  Instagram,
  Youtube,
  Smartphone,
  Play,
  Hash,
  Search,
  MoreHorizontal,
  CheckCircle2,
  XCircle,
  Loader2,
  Building2,
  Link2,
  Eye,
  ChevronDown,
  AlertCircle,
  UserPlus,
  Music,
  Plug,
  BarChart3,
  Star,
  TrendingUp,
  Lock,
  Clock,
  Zap,
  RefreshCw,
  X,
  Info,
  ShieldCheck,
  Radar,
  MessageSquare,
  Tag,
  Megaphone,
  Newspaper,
  Activity,
  MapPin,
  Brain,
  Target,
  FileText,
  Sparkles,
  ArrowUpRight,
  Filter,
} from "lucide-react";

/* ─────────────── TikTok icon ─────────────── */
function TikTokIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z" />
    </svg>
  );
}

/* ─────────────── Competitor Logo with fallback ─────────────── */
function CompetitorLogo({ name, logoUrl }: { name: string; logoUrl?: string }) {
  const [failed, setFailed] = useState(false);
  if (!logoUrl || failed) {
    return (
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 text-sm font-bold text-violet-700 shrink-0">
        {name.charAt(0).toUpperCase()}
      </div>
    );
  }
  return (
    <img src={logoUrl} alt={name} className="h-10 w-10 rounded-xl object-contain bg-white border border-border/50 shrink-0" onError={() => setFailed(true)} />
  );
}

/* ─────────────── Channel config ─────────────── */
const CHANNELS = [
  { key: "facebook_page_id", label: "Facebook", icon: Globe, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200", placeholder: "Page ID Facebook" },
  { key: "instagram_username", label: "Instagram", icon: Instagram, color: "text-pink-500", bg: "bg-pink-50", border: "border-pink-200", placeholder: "@username" },
  { key: "tiktok_username", label: "TikTok", icon: TikTokIcon, color: "text-slate-800", bg: "bg-slate-50", border: "border-slate-200", placeholder: "@username" },
  { key: "youtube_channel_id", label: "YouTube", icon: Youtube, color: "text-red-500", bg: "bg-red-50", border: "border-red-200", placeholder: "UCxxxxxx" },
  { key: "snapchat_entity_name", label: "Snapchat", icon: Hash, color: "text-yellow-500", bg: "bg-yellow-50", border: "border-yellow-200", placeholder: "Nom sur Snapchat Ads" },
  { key: "playstore_app_id", label: "Google Play", icon: Play, color: "text-green-600", bg: "bg-green-50", border: "border-green-200", placeholder: "com.example.app" },
  { key: "appstore_app_id", label: "App Store", icon: Smartphone, color: "text-sky-500", bg: "bg-sky-50", border: "border-sky-200", placeholder: "123456789" },
] as const;

export default function CompetitorsPage() {
  const [competitors, setCompetitors] = useState<any[]>([]);
  const [freshness, setFreshness] = useState<FreshnessData | null>(null);
  const [storeCounts, setStoreCounts] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [enrichResult, setEnrichResult] = useState<any>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCompetitor, setEditingCompetitor] = useState<Competitor | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [formData, setFormData] = useState<CompetitorCreate>({
    name: "",
    website: "",
    facebook_page_id: "",
    instagram_username: "",
    tiktok_username: "",
    youtube_channel_id: "",
    snapchat_entity_name: "",
    playstore_app_id: "",
    appstore_app_id: "",
  });

  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [childPageIds, setChildPageIds] = useState<string[]>([]);
  const [childSuggestions, setChildSuggestions] = useState<any[]>([]);
  const [detectingChildren, setDetectingChildren] = useState(false);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const lookupTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleNameChange = useCallback((value: string) => {
    setFormData((prev) => ({ ...prev, name: value }));
    if (editingCompetitor || value.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    if (lookupTimer.current) clearTimeout(lookupTimer.current);
    lookupTimer.current = setTimeout(async () => {
      try {
        const results = await competitorsAPI.lookup(value);
        setSuggestions(results);
        setShowSuggestions(results.length > 0);
      } catch {
        setSuggestions([]);
      }
    }, 250);
  }, [editingCompetitor]);

  function applySuggestion(s: any) {
    setFormData({
      name: s.name,
      website: s.website || "",
      facebook_page_id: s.facebook_page_id || "",
      instagram_username: s.instagram_username || "",
      tiktok_username: s.tiktok_username || "",
      youtube_channel_id: s.youtube_channel_id || "",
      snapchat_entity_name: s.snapchat_entity_name || "",
      playstore_app_id: s.playstore_app_id || "",
      appstore_app_id: s.appstore_app_id || "",
    });
    setSuggestions([]);
    setShowSuggestions(false);
  }

  useEffect(() => {
    loadCompetitors();
  }, []);

  async function loadCompetitors() {
    try {
      const data = await competitorsAPI.list();
      setCompetitors(data);

      // Fetch freshness
      try {
        const { freshnessAPI } = await import("@/lib/api");
        const f = await freshnessAPI.get();
        setFreshness(f);
      } catch {}

      // Fetch store counts
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
        const res = await fetch(`${API_BASE}/geo/competitor-stores`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const storeData = await res.json();
          const counts: Record<number, number> = {};
          for (const group of storeData.competitors || []) {
            counts[group.competitor_id] = group.total;
          }
          setStoreCounts(counts);
        }
      } catch {}
    } catch (err) {
      console.error("Failed to load competitors:", err);
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setFormData({
      name: "",
      website: "",
      facebook_page_id: "",
      instagram_username: "",
      tiktok_username: "",
      youtube_channel_id: "",
      snapchat_entity_name: "",
      playstore_app_id: "",
      appstore_app_id: "",
    });
    setEditingCompetitor(null);
    setChildPageIds([]);
    setChildSuggestions([]);
  }

  function handleEdit(competitor: Competitor) {
    setEditingCompetitor(competitor);
    setFormData({
      name: competitor.name,
      website: competitor.website || "",
      facebook_page_id: competitor.facebook_page_id || "",
      instagram_username: competitor.instagram_username || "",
      tiktok_username: competitor.tiktok_username || "",
      youtube_channel_id: competitor.youtube_channel_id || "",
      snapchat_entity_name: competitor.snapchat_entity_name || "",
      playstore_app_id: competitor.playstore_app_id || "",
      appstore_app_id: competitor.appstore_app_id || "",
    });
    // Load existing child page IDs
    try {
      const existing = (competitor as any).child_page_ids;
      setChildPageIds(existing ? JSON.parse(existing) : []);
    } catch { setChildPageIds([]); }
    setChildSuggestions([]);
    setDialogOpen(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingCompetitor) {
        const updateData = {
          ...formData,
          child_page_ids: childPageIds.length > 0 ? JSON.stringify(childPageIds) : null,
        };
        await competitorsAPI.update(editingCompetitor.id, updateData);
      } else {
        await competitorsAPI.create(formData);
      }
      await loadCompetitors();
      setDialogOpen(false);
      resetForm();
    } catch (err) {
      console.error("Failed to save competitor:", err);
    }
  }

  async function handleDelete(competitor: Competitor) {
    if (!confirm(`Supprimer ${competitor.name} ?`)) return;
    try {
      await competitorsAPI.delete(competitor.id);
      await loadCompetitors();
    } catch (err) {
      console.error("Failed to delete competitor:", err);
    }
  }

  const filteredCompetitors = competitors.filter((c) =>
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  function getChannelCount(comp: any) {
    return CHANNELS.filter((ch) => comp[ch.key]).length;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement des concurrents...</span>
        </div>
      </div>
    );
  }

  async function handleEnrichAll() {
    setEnriching(true);
    setEnrichResult(null);
    try {
      const result = await enrichAPI.enrichAll();
      setEnrichResult(result);
      loadCompetitors(); // Refresh data
    } catch (err: any) {
      setEnrichResult({ message: `Erreur: ${err.message}`, errors: 1 });
    } finally {
      setEnriching(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
            <Users className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Concurrents</h1>
            <p className="text-[13px] text-muted-foreground flex items-center gap-2">
              {competitors.length} concurrent{competitors.length !== 1 ? "s" : ""} suivi{competitors.length !== 1 ? "s" : ""}
              {freshness && <FreshnessBadge timestamp={freshness.instagram || freshness.tiktok || freshness.ads_snapchat || freshness.playstore} />}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="gap-2 shadow-sm" onClick={handleEnrichAll} disabled={enriching || competitors.length === 0}>
            {enriching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {enriching ? "Enrichissement..." : "Enrichir tout"}
          </Button>
          <Dialog
            open={dialogOpen}
            onOpenChange={(open) => {
              setDialogOpen(open);
              if (!open) resetForm();
            }}
          >
            <DialogTrigger asChild>
              <Button className="gap-2 shadow-sm">
                <UserPlus className="h-4 w-4" />
                Ajouter
              </Button>
            </DialogTrigger>
          <DialogContent className="sm:max-w-[560px]">
            <form onSubmit={handleSubmit}>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-100">
                    {editingCompetitor ? (
                      <Pencil className="h-5 w-5 text-violet-600" />
                    ) : (
                      <UserPlus className="h-5 w-5 text-violet-600" />
                    )}
                  </div>
                  <div>
                    <DialogTitle className="text-lg">
                      {editingCompetitor ? "Modifier le concurrent" : "Ajouter un concurrent"}
                    </DialogTitle>
                    <DialogDescription className="text-[13px]">
                      Renseignez les informations et les identifiants de suivi.
                    </DialogDescription>
                  </div>
                </div>
              </DialogHeader>

              <div className="space-y-5 py-5">
                {/* Basic info */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1.5 relative">
                    <Label htmlFor="name" className="text-xs font-medium flex items-center gap-1.5">
                      <Building2 className="h-3 w-3 text-muted-foreground" />
                      Nom *
                    </Label>
                    <Input
                      id="name"
                      ref={nameInputRef}
                      value={formData.name}
                      onChange={(e) => handleNameChange(e.target.value)}
                      onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                      onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                      placeholder="Carrefour"
                      required
                      autoComplete="off"
                      className="h-9"
                    />
                    {showSuggestions && suggestions.length > 0 && (
                      <div ref={suggestionsRef} className="absolute z-50 top-full left-0 right-0 mt-1 rounded-lg border border-border bg-white shadow-lg max-h-48 overflow-y-auto">
                        {suggestions.map((s) => {
                          const channels = [
                            s.instagram_username && "Instagram",
                            s.tiktok_username && "TikTok",
                            s.youtube_channel_id && "YouTube",
                            s.playstore_app_id && "Play Store",
                            s.appstore_app_id && "App Store",
                          ].filter(Boolean);
                          return (
                            <button
                              key={s.name}
                              type="button"
                              onMouseDown={(e) => { e.preventDefault(); applySuggestion(s); }}
                              className="w-full text-left px-3 py-2 hover:bg-violet-50 flex items-center justify-between gap-2 transition-colors"
                            >
                              <div>
                                <span className="text-sm font-medium text-foreground">{s.name}</span>
                                {s.website && <span className="text-[11px] text-muted-foreground ml-2">{s.website.replace("https://www.", "")}</span>}
                              </div>
                              {channels.length > 0 && (
                                <span className="text-[10px] text-muted-foreground shrink-0">
                                  {channels.length} canaux
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="website" className="text-xs font-medium flex items-center gap-1.5">
                      <Globe className="h-3 w-3 text-muted-foreground" />
                      Site web
                    </Label>
                    <Input
                      id="website"
                      type="url"
                      value={formData.website}
                      onChange={(e) => setFormData({ ...formData, website: e.target.value })}
                      placeholder="https://carrefour.fr"
                      className="h-9"
                    />
                  </div>
                </div>

                {/* Channels */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Link2 className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Canaux de suivi
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {CHANNELS.map((ch) => {
                      const Icon = ch.icon;
                      return (
                        <div key={ch.key} className="space-y-1.5">
                          <Label htmlFor={ch.key} className="text-xs flex items-center gap-1.5">
                            <Icon className={`h-3.5 w-3.5 ${ch.color}`} />
                            {ch.label}
                          </Label>
                          <Input
                            id={ch.key}
                            value={(formData as any)[ch.key] || ""}
                            onChange={(e) => setFormData({ ...formData, [ch.key]: e.target.value })}
                            placeholder={ch.placeholder}
                            className="h-9 text-sm"
                          />
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Child pages (pages filles) — only in edit mode */}
              {editingCompetitor && (
                <div className="space-y-3 pt-2 border-t">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-semibold flex items-center gap-1.5">
                      <Globe className="h-3.5 w-3.5 text-violet-500" />
                      Pages filles (sous-pages Facebook)
                    </Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs gap-1"
                      disabled={detectingChildren}
                      onClick={async () => {
                        setDetectingChildren(true);
                        try {
                          const res = await competitorsAPI.suggestChildPages(editingCompetitor.id);
                          setChildSuggestions(res.suggestions || []);
                        } catch (err) {
                          console.error("Failed to detect child pages:", err);
                        } finally {
                          setDetectingChildren(false);
                        }
                      }}
                    >
                      {detectingChildren ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Search className="h-3 w-3" />}
                      Detecter
                    </Button>
                  </div>
                  {/* Current child pages */}
                  <div className="flex flex-wrap gap-1.5">
                    {childPageIds.map((pid) => (
                      <span key={pid} className="inline-flex items-center gap-1 text-xs bg-violet-50 text-violet-700 border border-violet-200 px-2 py-1 rounded-full">
                        {pid}
                        <button
                          type="button"
                          onClick={() => setChildPageIds(prev => prev.filter(id => id !== pid))}
                          className="text-violet-400 hover:text-violet-600"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))}
                    {childPageIds.length === 0 && <span className="text-xs text-muted-foreground">Aucune page fille configuree</span>}
                  </div>
                  {/* Suggestions */}
                  {childSuggestions.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Suggestions</span>
                      {childSuggestions.filter(s => !childPageIds.includes(s.page_id)).map((s) => (
                        <div key={s.page_id} className="flex items-center justify-between text-xs bg-muted/50 rounded-lg px-3 py-2">
                          <span>
                            <span className="font-medium">{s.page_name}</span>
                            <span className="text-muted-foreground ml-1.5">({s.page_id})</span>
                            {s.ad_count > 0 && <span className="text-muted-foreground ml-1">- {s.ad_count} pubs</span>}
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-6 text-xs gap-1 text-violet-600"
                            onClick={() => setChildPageIds(prev => [...prev, s.page_id])}
                          >
                            <Plus className="h-3 w-3" /> Ajouter
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <DialogFooter className="gap-2">
                <Button type="button" variant="outline" onClick={() => { setDialogOpen(false); resetForm(); }}>
                  Annuler
                </Button>
                <Button type="submit" className="gap-1.5">
                  {editingCompetitor ? (
                    <>
                      <CheckCircle2 className="h-4 w-4" />
                      Sauvegarder
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4" />
                      Ajouter
                    </>
                  )}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* ── Enrichment result banner ── */}
      {enrichResult && (
        <div className={`rounded-xl border px-4 py-3 ${enrichResult.errors > 0 && enrichResult.ok === 0 ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800" : "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-800"}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {enrichResult.errors > 0 && enrichResult.ok === 0 ? (
                <AlertCircle className="h-4 w-4 text-red-600" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              )}
              <span className="text-sm font-medium">{enrichResult.message}</span>
            </div>
            <button onClick={() => setEnrichResult(null)} className="text-muted-foreground hover:text-foreground">
              <XCircle className="h-4 w-4" />
            </button>
          </div>
          {enrichResult.details && enrichResult.errors > 0 && (() => {
            const errors = enrichResult.details.filter((d: any) => d.status === "error");
            const grouped = errors.reduce((acc: Record<string, string[]>, d: any) => {
              const reason = d.reason || "unknown";
              if (!acc[reason]) acc[reason] = [];
              acc[reason].push(`${d.competitor || "?"} (${d.platform || "?"})`);
              return acc;
            }, {} as Record<string, string[]>);
            return (
              <div className="mt-2 space-y-1">
                {Object.entries(grouped).slice(0, 5).map(([reason, items]) => (
                  <div key={reason} className="text-xs text-red-700 dark:text-red-400">
                    <span className="font-medium">{(items as string[]).length}x</span> {reason}
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      )}

      {/* ── Search bar ── */}
      {competitors.length > 0 && (
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/60" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher un concurrent..."
            className="pl-9 h-9"
          />
        </div>
      )}

      {/* ── Competitor cards ── */}
      {filteredCompetitors.length === 0 && competitors.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-border bg-card/50 p-12 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50">
              <UserPlus className="h-7 w-7 text-violet-400" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-1">Aucun concurrent</h3>
          <p className="text-sm text-muted-foreground mb-4 max-w-md mx-auto">
            Commencez par ajouter vos concurrents pour démarrer la veille.
            Vous pouvez aussi les configurer depuis Mon enseigne.
          </p>
          <Button onClick={() => setDialogOpen(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            Ajouter votre premier concurrent
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredCompetitors.map((comp) => {
            const channelCount = getChannelCount(comp);
            return (
              <div
                key={comp.id}
                className="rounded-xl border bg-card overflow-hidden transition-all hover:shadow-md hover:border-violet-200/60 group"
              >
                {/* Card header */}
                <div className="p-4 pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      <CompetitorLogo name={comp.name} logoUrl={comp.logo_url} />
                      <div className="min-w-0">
                        <h3 className="font-semibold text-[15px] text-foreground truncate">{comp.name}</h3>
                        {comp.website ? (
                          <a
                            href={comp.website.startsWith("http") ? comp.website : `https://${comp.website}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-[12px] text-muted-foreground hover:text-violet-600 transition-colors"
                          >
                            <Globe className="h-3 w-3" />
                            {(() => { try { return new URL(comp.website.startsWith("http") ? comp.website : `https://${comp.website}`).hostname; } catch { return comp.website; } })()}
                            <ExternalLink className="h-2.5 w-2.5 opacity-60" />
                          </a>
                        ) : (
                          <span className="text-[12px] text-muted-foreground/60">Pas de site web</span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handleEdit(comp)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity text-red-500 hover:text-red-600 hover:bg-red-50"
                        onClick={() => handleDelete(comp)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </div>

                {/* Channel badges */}
                <div className="px-4 pb-4">
                  <div className="flex items-center gap-1 mb-2">
                    <Link2 className="h-3 w-3 text-muted-foreground/50" />
                    <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                      {channelCount} cana{channelCount !== 1 ? "ux" : "l"}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {CHANNELS.map((ch) => {
                      const value = comp[ch.key];
                      const Icon = ch.icon;
                      if (!value) return (
                        <div
                          key={ch.key}
                          className="flex items-center gap-1 rounded-full px-2 py-1 text-[10px] bg-muted/40 text-muted-foreground/40 border border-transparent"
                        >
                          <Icon className="h-3 w-3" />
                          <span>{ch.label}</span>
                        </div>
                      );
                      return (
                        <div
                          key={ch.key}
                          className={`flex items-center gap-1 rounded-full px-2 py-1 text-[10px] font-medium ${ch.bg} ${ch.color} border ${ch.border}`}
                        >
                          <Icon className="h-3 w-3" />
                          <span>{ch.label}</span>
                          <CheckCircle2 className="h-2.5 w-2.5 opacity-60" />
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Footer */}
                <div className="px-4 py-2.5 bg-muted/20 border-t flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-muted-foreground">
                      Ajouté le {formatDate(comp.created_at)}
                    </span>
                    {storeCounts[comp.id] > 0 && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-orange-600 bg-orange-50 border border-orange-200 rounded-full px-2 py-0.5">
                        <Building2 className="h-2.5 w-2.5" />
                        {storeCounts[comp.id]} magasin{storeCounts[comp.id] > 1 ? "s" : ""}
                      </span>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-[11px] text-violet-600 hover:text-violet-700 hover:bg-violet-50 gap-1 px-2"
                    onClick={() => handleEdit(comp)}
                  >
                    <Eye className="h-3 w-3" />
                    Détails
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════ */}
      {/* Section : Sources de veille concurrentielle                       */}
      {/* ═══════════════════════════════════════════════════════════════════ */}
      {competitors.length > 0 && <CompetitiveSourcesSection />}
    </div>
  );
}

/* ─────────────── Competitive Intelligence Sources ─────────────── */

type SourceCategory = "seo" | "social" | "ads" | "apps" | "pricing" | "reputation" | "tech" | "geo" | "analytics";

const CATEGORY_CONFIG: Record<SourceCategory, { label: string; icon: any }> = {
  seo: { label: "SEO", icon: Globe },
  social: { label: "Social", icon: Activity },
  ads: { label: "Publicite", icon: Megaphone },
  apps: { label: "Apps", icon: Smartphone },
  pricing: { label: "Prix", icon: Tag },
  reputation: { label: "Reputation", icon: Star },
  tech: { label: "Tech", icon: ShieldCheck },
  geo: { label: "GEO / IA", icon: Brain },
  analytics: { label: "Analytics", icon: BarChart3 },
};

interface CISource {
  id: string;
  name: string;
  description: string;
  icon: any;
  color: string;
  bg: string;
  border: string;
  status: "active" | "available" | "coming_soon";
  category: SourceCategory;
  purpose: string;
  url: string;
  badge?: string;
  syncLabel?: string;
}

const CI_SOURCES: CISource[] = [
  // --- Active (demo) ---
  {
    id: "similarweb", name: "SimilarWeb", description: "Trafic web, sources, audience des concurrents",
    icon: BarChart3, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200",
    status: "active", category: "analytics", purpose: "Vue d'ensemble → Trafic web & audience",
    url: "https://www.similarweb.com", badge: "4 domaines suivis", syncLabel: "Synchro hebdo",
  },
  {
    id: "semrush", name: "Semrush", description: "Mots-cles, backlinks, positions SEO concurrents",
    icon: TrendingUp, color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200",
    status: "active", category: "seo", purpose: "SEO → Positions & mots-cles",
    url: "https://www.semrush.com", badge: "1.2k keywords suivis", syncLabel: "Synchro il y a 6h",
  },
  {
    id: "mention", name: "Mention / Brand24", description: "Alertes medias, mentions web et reseaux sociaux",
    icon: Radar, color: "text-violet-600", bg: "bg-violet-50", border: "border-violet-200",
    status: "active", category: "reputation", purpose: "Concurrents → Alertes & mentions",
    url: "https://mention.com", badge: "342 mentions/sem", syncLabel: "Temps reel",
  },
  {
    id: "reviews_agg", name: "Avis clients agreges", description: "Google, Trustpilot, App Store, Play Store",
    icon: Star, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200",
    status: "active", category: "reputation", purpose: "Applications → Notes & avis agrégés",
    url: "https://www.trustpilot.com", badge: "4.2 note moyenne secteur", syncLabel: "Synchro quotidienne",
  },
  // --- Available ---
  {
    id: "prisync", name: "Prisync", description: "Suivi des prix concurrents en temps reel",
    icon: Tag, color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200",
    status: "available", category: "pricing", purpose: "Concurrents → Benchmark tarifaire",
    url: "https://prisync.com",
  },
  {
    id: "dataai", name: "data.ai (App Annie)", description: "Classements, telechargements, revenus apps",
    icon: Smartphone, color: "text-sky-600", bg: "bg-sky-50", border: "border-sky-200",
    status: "available", category: "apps", purpose: "Applications → Classements & downloads",
    url: "https://www.data.ai",
  },
  {
    id: "sprout", name: "Sprout Social", description: "Benchmark reseaux sociaux, engagement concurrents",
    icon: Activity, color: "text-green-600", bg: "bg-green-50", border: "border-green-200",
    status: "available", category: "social", purpose: "Reseaux sociaux → Engagement & benchmark",
    url: "https://sproutsocial.com",
  },
  {
    id: "google_alerts", name: "Google Alerts", description: "Alertes actualites et presse sur les concurrents",
    icon: Newspaper, color: "text-red-500", bg: "bg-red-50", border: "border-red-200",
    status: "available", category: "reputation", purpose: "Concurrents → Veille presse & actualites",
    url: "https://www.google.com/alerts",
  },
  {
    id: "meta_adlib", name: "Meta Ad Library API", description: "Transparence publicitaire Facebook & Instagram",
    icon: Megaphone, color: "text-blue-500", bg: "bg-blue-50", border: "border-blue-200",
    status: "available", category: "ads", purpose: "Publicites → Creatives Facebook & Instagram",
    url: "https://www.facebook.com/ads/library",
  },
  {
    id: "wappalyzer", name: "Wappalyzer / BuiltWith", description: "Stack technique des sites concurrents",
    icon: ShieldCheck, color: "text-indigo-600", bg: "bg-indigo-50", border: "border-indigo-200",
    status: "available", category: "tech", purpose: "Concurrents → Stack technique & outils",
    url: "https://www.wappalyzer.com",
  },
  {
    id: "ahrefs", name: "Ahrefs", description: "Backlinks, domaines referents, audit SEO concurrents",
    icon: Globe, color: "text-orange-500", bg: "bg-orange-50", border: "border-orange-200",
    status: "available", category: "seo", purpose: "SEO → Backlinks & autorite domaine",
    url: "https://ahrefs.com",
  },
  {
    id: "socialbakers", name: "Emplifi (Socialbakers)", description: "Analytics social cross-plateforme, benchmarks secteur",
    icon: Activity, color: "text-pink-600", bg: "bg-pink-50", border: "border-pink-200",
    status: "available", category: "social", purpose: "Reseaux sociaux → Analytics cross-plateforme",
    url: "https://emplifi.io",
  },
  {
    id: "google_ads_transparency", name: "Google Ads Transparency", description: "Creatives Google Ads concurrents, historique",
    icon: Megaphone, color: "text-green-500", bg: "bg-green-50", border: "border-green-200",
    status: "available", category: "ads", purpose: "Publicites → Creatives Google Ads",
    url: "https://adstransparency.google.com",
  },
  {
    id: "screaming_frog", name: "Screaming Frog", description: "Audit technique SEO, crawl de sites concurrents",
    icon: Search, color: "text-lime-600", bg: "bg-lime-50", border: "border-lime-200",
    status: "available", category: "seo", purpose: "SEO → Audit technique on-site",
    url: "https://www.screamingfrog.co.uk",
  },
  {
    id: "apptopia", name: "Apptopia", description: "Estimations telechargements, revenus, SDK concurrents",
    icon: Smartphone, color: "text-purple-600", bg: "bg-purple-50", border: "border-purple-200",
    status: "available", category: "apps", purpose: "Applications → Revenus & SDK",
    url: "https://apptopia.com",
  },
  {
    id: "google_maps", name: "Google Maps / GMB", description: "Fiches etablissements, avis locaux, photos",
    icon: MapPin, color: "text-red-600", bg: "bg-red-50", border: "border-red-200",
    status: "available", category: "geo", purpose: "Carte & Zones → Fiches GMB & avis locaux",
    url: "https://business.google.com",
  },
  {
    id: "mistral_api", name: "Mistral AI", description: "Visibilite de marque dans les reponses Mistral / Le Chat",
    icon: Brain, color: "text-orange-600", bg: "bg-orange-50", border: "border-orange-200",
    status: "available", category: "geo", purpose: "GEO → Part de voix IA Mistral",
    url: "https://mistral.ai",
  },
  {
    id: "claude_api", name: "Anthropic / Claude", description: "Visibilite de marque dans les reponses Claude",
    icon: Brain, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200",
    status: "available", category: "geo", purpose: "GEO → Part de voix IA Claude",
    url: "https://anthropic.com",
  },
  {
    id: "gemini_api", name: "Google / Gemini", description: "Visibilite de marque dans les reponses Gemini",
    icon: Brain, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200",
    status: "available", category: "geo", purpose: "GEO → Part de voix IA Gemini",
    url: "https://ai.google.dev",
  },
  {
    id: "chatgpt_api", name: "OpenAI / ChatGPT", description: "Visibilite de marque dans les reponses ChatGPT",
    icon: Brain, color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-200",
    status: "available", category: "geo", purpose: "GEO → Part de voix IA ChatGPT",
    url: "https://platform.openai.com",
  },
  // --- Coming soon ---
  {
    id: "adthena", name: "Adthena", description: "Intelligence Search Ads concurrents, share of voice",
    icon: Megaphone, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200",
    status: "coming_soon", category: "ads", purpose: "Publicites → Share of voice Search Ads",
    url: "https://www.adthena.com",
  },
  {
    id: "gartner", name: "Gartner Digital IQ", description: "Benchmark digital, scoring concurrentiel",
    icon: BarChart3, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200",
    status: "coming_soon", category: "analytics", purpose: "Vue d'ensemble → Score digital global",
    url: "https://www.gartner.com",
  },
  {
    id: "brandwatch", name: "Brandwatch", description: "Social listening avance, analyse de sentiment",
    icon: Radar, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200",
    status: "coming_soon", category: "social", purpose: "Reseaux sociaux → Sentiment & tendances",
    url: "https://www.brandwatch.com",
  },
  {
    id: "price_observatory", name: "Price Observatory", description: "Comparateur prix grande distribution en temps reel",
    icon: Tag, color: "text-gray-500", bg: "bg-gray-50", border: "border-gray-200",
    status: "coming_soon", category: "pricing", purpose: "Concurrents → Suivi prix grande distribution",
    url: "https://priceobservatory.com",
  },
];

function CompetitiveSourcesSection() {
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const activeCount = CI_SOURCES.filter(s => s.status === "active").length;

  function handleConnect(id: string) {
    setConnectingId(id);
    setTimeout(() => setConnectingId(null), 2000);
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-cyan-100 to-blue-100">
              <Radar className="h-5 w-5 text-cyan-600" />
            </div>
            <div>
              <CardTitle className="text-lg">Sources de veille</CardTitle>
              <p className="text-sm text-muted-foreground">
                {activeCount} source{activeCount > 1 ? "s" : ""} active{activeCount > 1 ? "s" : ""} sur {CI_SOURCES.length} disponibles
              </p>
            </div>
          </div>
          <span className="hidden sm:flex items-center gap-1.5 text-[11px] text-cyan-600 bg-cyan-50 border border-cyan-200 px-2.5 py-1 rounded-full font-medium">
            <Zap className="h-3 w-3" />
            Enrichissement auto
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {CI_SOURCES.map(source => {
            const Icon = source.icon;
            const isConnecting = connectingId === source.id;
            return (
              <div
                key={source.id}
                className={`relative rounded-xl border p-4 transition-all ${
                  source.status === "active"
                    ? `${source.bg} ${source.border} border-2`
                    : source.status === "coming_soon"
                    ? "bg-gray-50/50 border-dashed border-gray-200 opacity-75"
                    : "bg-white border-gray-200 hover:border-gray-300 hover:shadow-sm"
                }`}
              >
                {source.status === "active" && (
                  <div className="absolute top-3 right-3">
                    <span className="flex items-center gap-1 rounded-full bg-emerald-100 border border-emerald-200 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      Actif
                    </span>
                  </div>
                )}
                {source.status === "coming_soon" && (
                  <div className="absolute top-3 right-3">
                    <span className="flex items-center gap-1 rounded-full bg-gray-100 border border-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                      <Clock className="h-2.5 w-2.5" />
                      Bientot
                    </span>
                  </div>
                )}

                <div className="flex items-start gap-3">
                  <div className={`flex h-10 w-10 items-center justify-center rounded-lg shrink-0 ${
                    source.status === "active" ? "bg-white shadow-sm" : source.bg
                  }`}>
                    <Icon className={`h-5 w-5 ${source.color}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-semibold ${
                      source.status === "coming_soon" ? "text-gray-500" : "text-foreground"
                    }`}>
                      {source.name}
                    </p>
                    <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                      {source.description}
                    </p>
                  </div>
                </div>

                {source.status === "active" && (
                  <div className="mt-3 pt-3 border-t border-current/10 space-y-1.5">
                    {source.badge && (
                      <span className={`text-xs font-bold ${source.color}`}>{source.badge}</span>
                    )}
                    {source.syncLabel && (
                      <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                        <RefreshCw className="h-2.5 w-2.5" />
                        {source.syncLabel}
                      </div>
                    )}
                  </div>
                )}

                {source.status === "available" && (
                  <div className="mt-3">
                    <button
                      onClick={() => handleConnect(source.id)}
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

                {source.status === "coming_soon" && (
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

        <div className="flex items-center gap-2 text-[11px] text-muted-foreground bg-gradient-to-r from-cyan-50 to-blue-50 rounded-lg px-4 py-3 border border-cyan-100">
          <Info className="h-3.5 w-3.5 text-cyan-500 shrink-0" />
          <span>
            Les sources de veille alimentent automatiquement les analyses par concurrent : trafic, prix, avis, publicites, SEO et reseaux sociaux.
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
