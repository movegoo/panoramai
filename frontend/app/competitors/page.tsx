"use client";

import { useEffect, useState } from "react";
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
import { competitorsAPI, Competitor, CompetitorCreate, API_BASE } from "@/lib/api";
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
} from "lucide-react";

/* ─────────────── TikTok icon ─────────────── */
function TikTokIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor">
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z" />
    </svg>
  );
}

/* ─────────────── Channel config ─────────────── */
const CHANNELS = [
  { key: "facebook_page_id", label: "Facebook", icon: Globe, color: "text-blue-600", bg: "bg-blue-50", border: "border-blue-200", placeholder: "Page ID Facebook" },
  { key: "instagram_username", label: "Instagram", icon: Instagram, color: "text-pink-500", bg: "bg-pink-50", border: "border-pink-200", placeholder: "@username" },
  { key: "tiktok_username", label: "TikTok", icon: TikTokIcon, color: "text-slate-800", bg: "bg-slate-50", border: "border-slate-200", placeholder: "@username" },
  { key: "youtube_channel_id", label: "YouTube", icon: Youtube, color: "text-red-500", bg: "bg-red-50", border: "border-red-200", placeholder: "UCxxxxxx" },
  { key: "playstore_app_id", label: "Google Play", icon: Play, color: "text-green-600", bg: "bg-green-50", border: "border-green-200", placeholder: "com.example.app" },
  { key: "appstore_app_id", label: "App Store", icon: Smartphone, color: "text-sky-500", bg: "bg-sky-50", border: "border-sky-200", placeholder: "123456789" },
] as const;

export default function CompetitorsPage() {
  const [competitors, setCompetitors] = useState<any[]>([]);
  const [storeCounts, setStoreCounts] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
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
    playstore_app_id: "",
    appstore_app_id: "",
  });

  useEffect(() => {
    loadCompetitors();
  }, []);

  async function loadCompetitors() {
    try {
      const data = await competitorsAPI.list();
      setCompetitors(data);

      // Fetch store counts
      try {
        const res = await fetch(`${API_BASE}/geo/competitor-stores`);
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
      playstore_app_id: "",
      appstore_app_id: "",
    });
    setEditingCompetitor(null);
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
      playstore_app_id: competitor.playstore_app_id || "",
      appstore_app_id: competitor.appstore_app_id || "",
    });
    setDialogOpen(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingCompetitor) {
        await competitorsAPI.update(editingCompetitor.id, formData);
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
            <p className="text-[13px] text-muted-foreground">
              {competitors.length} concurrent{competitors.length !== 1 ? "s" : ""} suivi{competitors.length !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
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
              Ajouter un concurrent
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
                  <div className="space-y-1.5">
                    <Label htmlFor="name" className="text-xs font-medium flex items-center gap-1.5">
                      <Building2 className="h-3 w-3 text-muted-foreground" />
                      Nom *
                    </Label>
                    <Input
                      id="name"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="Carrefour"
                      required
                      className="h-9"
                    />
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
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 text-sm font-bold text-violet-700 shrink-0">
                        {comp.name.charAt(0).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-[15px] text-foreground truncate">{comp.name}</h3>
                        {comp.website ? (
                          <a
                            href={comp.website}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-[12px] text-muted-foreground hover:text-violet-600 transition-colors"
                          >
                            <Globe className="h-3 w-3" />
                            {new URL(comp.website).hostname}
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
                      {channelCount} canal{channelCount !== 1 ? "x" : ""}
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
    </div>
  );
}
