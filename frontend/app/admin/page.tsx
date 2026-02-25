"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  adminAPI,
  freshnessAPI,
  AdminStats,
  AdminUser,
  PromptTemplateData,
  GpsConflictsResponse,
  PagesAuditSector,
  PagesAuditCompetitor,
  SectorItem,
  FreshnessData,
} from "@/lib/api";
import {
  Users,
  Store,
  Target,
  Megaphone,
  MapPin,
  Smartphone,
  Instagram,
  Youtube,
  Music,
  Clock,
  CheckCircle,
  XCircle,
  Shield,
  Sparkles,
  Save,
  X,
  Navigation,
  AlertTriangle,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Globe,
  Facebook,
  Ghost,
  Trash2,
  Eye,
  Search,
  Layers,
  Pencil,
  Key,
  Activity,
  RefreshCw,
} from "lucide-react";
import { FreshnessBadge } from "@/components/freshness-badge";

function StatCard({
  label,
  value,
  icon: Icon,
  sub,
}: {
  label: string;
  value: number | string;
  icon: any;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-50 text-violet-600">
          <Icon className="h-4.5 w-4.5" />
        </div>
        <div>
          <p className="text-2xl font-bold text-foreground">{value}</p>
          <p className="text-xs text-muted-foreground">{label}</p>
          {sub && <p className="text-[10px] text-muted-foreground/70">{sub}</p>}
        </div>
      </div>
    </div>
  );
}

const PLATFORM_CONFIG: Record<string, { label: string; icon: any; color: string }> = {
  facebook: { label: "Facebook", icon: Facebook, color: "text-blue-600" },
  instagram: { label: "Instagram", icon: Instagram, color: "text-pink-500" },
  tiktok: { label: "TikTok", icon: Music, color: "text-foreground" },
  youtube: { label: "YouTube", icon: Youtube, color: "text-red-500" },
  snapchat: { label: "Snapchat", icon: Ghost, color: "text-yellow-500" },
  playstore: { label: "Play Store", icon: Smartphone, color: "text-green-600" },
  appstore: { label: "App Store", icon: Smartphone, color: "text-blue-500" },
  google: { label: "Google Ads", icon: Search, color: "text-amber-600" },
};

function PlatformBadge({ platform, count, configured }: { platform: string; count?: number; configured: boolean }) {
  const cfg = PLATFORM_CONFIG[platform];
  if (!cfg) return null;
  const Icon = cfg.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        configured
          ? "bg-emerald-50 text-emerald-700"
          : "bg-muted text-muted-foreground/50"
      }`}
    >
      <Icon className="h-3 w-3" />
      {count !== undefined && count > 0 ? count : configured ? "1" : "0"}
    </span>
  );
}

function CompetitorPagesRow({
  comp,
  onDelete,
  onUpdate,
}: {
  comp: PagesAuditCompetitor;
  onDelete: (competitorId: number, platform: string, pageId?: string) => Promise<void>;
  onUpdate?: (competitorId: number, field: string, value: string) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const p = comp.platforms;

  const startEdit = (field: string, currentValue: string) => {
    setEditingField(field);
    setEditValue(currentValue || "");
  };

  const saveEdit = async () => {
    if (!editingField || !onUpdate) return;
    setSaving(true);
    try {
      await onUpdate(comp.id, editingField, editValue);
      setEditingField(null);
    } finally {
      setSaving(false);
    }
  };

  const cancelEdit = () => {
    setEditingField(null);
    setEditValue("");
  };

  const handleDelete = async (platform: string, pageId?: string) => {
    const label = pageId || platform;
    if (!confirm(`Supprimer ${label} pour ${comp.name} ?`)) return;
    setDeleting(`${platform}:${pageId || ""}`);
    try {
      await onDelete(comp.id, platform, pageId);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="border-b border-border/50 last:border-0">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/30 transition-colors text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <ChevronRight
          className={`h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
        <span className="text-sm font-medium text-foreground min-w-[140px]">
          {comp.name}
          {comp.is_brand && (
            <span className="ml-1.5 text-[9px] bg-violet-100 text-violet-700 px-1.5 py-0.5 rounded-full font-medium">
              MARQUE
            </span>
          )}
        </span>
        <div className="flex items-center gap-1.5 flex-wrap flex-1">
          <PlatformBadge platform="facebook" count={p.facebook.total_pages} configured={p.facebook.total_pages > 0 || !!p.facebook.main_page_id} />
          <PlatformBadge platform="instagram" configured={p.instagram.configured} />
          <PlatformBadge platform="tiktok" configured={p.tiktok.configured} />
          <PlatformBadge platform="youtube" configured={p.youtube.configured} />
          {/* Snapchat masqué */}
          <PlatformBadge platform="playstore" configured={p.playstore.configured} />
          <PlatformBadge platform="appstore" configured={p.appstore.configured} />
          <PlatformBadge platform="google" count={p.google.ads_count} configured={p.google.configured} />
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pl-11 space-y-2">
          {/* Facebook pages */}
          <div className="rounded-lg bg-muted/30 p-3">
            <div className="flex items-center gap-2 mb-2">
              <Facebook className="h-3.5 w-3.5 text-blue-600" />
              <span className="text-xs font-semibold text-foreground">Facebook</span>
              {p.facebook.main_page_id && (
                <span className="text-[10px] text-muted-foreground font-mono">
                  page_id: {p.facebook.main_page_id}
                </span>
              )}
            </div>
            {p.facebook.detected_pages.length > 0 ? (
              <div className="space-y-1">
                {p.facebook.detected_pages.map((page) => (
                  <div key={page.page_id} className="flex items-center justify-between rounded bg-background px-3 py-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-foreground">{page.page_name}</span>
                      <span className="text-[10px] text-muted-foreground font-mono">{page.page_id}</span>
                      <span className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded-full">
                        {page.ads_count} ads
                      </span>
                      {page.page_id === p.facebook.main_page_id && (
                        <span className="text-[9px] bg-violet-100 text-violet-700 px-1 py-0.5 rounded">principal</span>
                      )}
                      {p.facebook.child_page_ids.includes(page.page_id) && (
                        <span className="text-[9px] bg-amber-100 text-amber-700 px-1 py-0.5 rounded">enfant</span>
                      )}
                    </div>
                    <button
                      className="p-1 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 disabled:opacity-30"
                      disabled={deleting === `facebook:${page.page_id}`}
                      onClick={() => handleDelete("facebook", page.page_id)}
                      title="Supprimer cette page et ses ads"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-muted-foreground">Aucune page detectee</p>
            )}
          </div>

          {/* Other platforms */}
          {(["instagram", "tiktok", "youtube", "playstore", "appstore"] as const).map((key) => {
            const plat = p[key];
            const cfg = PLATFORM_CONFIG[key];
            const fieldMap: Record<string, string> = { instagram: "instagram_username", tiktok: "tiktok_username", youtube: "youtube_channel_id", playstore: "playstore_app_id", appstore: "appstore_app_id" };
            const fieldName = fieldMap[key];
            const Icon = cfg.icon;
            return (
              <div key={key} className="flex items-center justify-between rounded-lg bg-muted/30 px-3 py-2">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <Icon className={`h-3.5 w-3.5 ${cfg.color} shrink-0`} />
                  <span className="text-xs font-medium text-foreground shrink-0">{cfg.label}</span>
                  {editingField === fieldName ? (
                    <div className="flex items-center gap-1 flex-1">
                      <input
                        autoFocus
                        className="text-[11px] font-mono bg-background border rounded px-2 py-0.5 flex-1 min-w-0"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") saveEdit(); if (e.key === "Escape") cancelEdit(); }}
                      />
                      <button onClick={saveEdit} disabled={saving} className="p-0.5 rounded hover:bg-emerald-50 text-emerald-600"><Save className="h-3 w-3" /></button>
                      <button onClick={cancelEdit} className="p-0.5 rounded hover:bg-muted text-muted-foreground"><X className="h-3 w-3" /></button>
                    </div>
                  ) : (
                    <>
                      <span className="text-[11px] text-muted-foreground font-mono truncate">{plat.handle || "—"}</span>
                      {onUpdate && (
                        <button onClick={() => startEdit(fieldName, plat.handle || "")} className="p-0.5 rounded hover:bg-muted text-muted-foreground hover:text-foreground shrink-0">
                          <Pencil className="h-3 w-3" />
                        </button>
                      )}
                    </>
                  )}
                </div>
                {!editingField && plat.handle && (
                  <button
                    className="p-1 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 disabled:opacity-30"
                    disabled={deleting === `${key}:`}
                    onClick={() => handleDelete(key)}
                    title={`Supprimer ${cfg.label}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            );
          })}

          {/* Snapchat masqué — pas assez de données pour l'instant */}

          {/* Google Ads */}
          {p.google.ads_count > 0 && (
            <div className="flex items-center justify-between rounded-lg bg-muted/30 px-3 py-2">
              <div className="flex items-center gap-2">
                <Search className="h-3.5 w-3.5 text-amber-600" />
                <span className="text-xs font-medium text-foreground">Google Ads</span>
                <span className="text-[10px] bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded-full">
                  {p.google.ads_count} ads
                </span>
              </div>
              <button
                className="p-1 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 disabled:opacity-30"
                disabled={deleting === "google:"}
                onClick={() => handleDelete("google")}
                title="Supprimer toutes les Google Ads"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Prompts state
  const [prompts, setPrompts] = useState<PromptTemplateData[]>([]);
  const [editingPrompt, setEditingPrompt] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [editModel, setEditModel] = useState("");
  const [editMaxTokens, setEditMaxTokens] = useState(1024);
  const [savingPrompt, setSavingPrompt] = useState(false);

  // GPS conflicts state
  const [gpsData, setGpsData] = useState<GpsConflictsResponse | null>(null);
  const [resolvingId, setResolvingId] = useState<number | null>(null);

  // Methodologies state
  const [methodologies, setMethodologies] = useState<{ module: string; icon: string; fields: { key: string; label: string; description: string }[] }[]>([]);
  const [openModule, setOpenModule] = useState<string | null>(null);

  // Pages audit state
  const [sectors, setSectors] = useState<SectorItem[]>([]);
  const [selectedSector, setSelectedSector] = useState<string>("");
  const [pagesAudit, setPagesAudit] = useState<PagesAuditSector[]>([]);
  const [pagesLoading, setPagesLoading] = useState(false);
  const [expandedSector, setExpandedSector] = useState<string | null>(null);

  // Dedup state
  const [deduplicating, setDeduplicating] = useState(false);

  // Re-enrich state
  const [reEnrichingAll, setReEnrichingAll] = useState(false);
  const [reEnrichingId, setReEnrichingId] = useState<number | null>(null);

  // Data health state
  const [dataHealth, setDataHealth] = useState<any>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // Freshness state
  const [freshness, setFreshness] = useState<FreshnessData | null>(null);

  // User editing state
  const [editingUser, setEditingUser] = useState<number | null>(null);
  const [editUserData, setEditUserData] = useState<{ name: string; email: string }>({ name: "", email: "" });
  const [savingUser, setSavingUser] = useState<number | null>(null);
  const [resetPasswordUser, setResetPasswordUser] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/");
    }
  }, [user, loading, router]);

  // Redirect non-admin users
  useEffect(() => {
    if (!loading && user && !user.is_admin) {
      router.replace("/");
    }
  }, [user, loading, router]);

  const loadPrompts = useCallback(() => {
    adminAPI.getPrompts().then(setPrompts).catch(() => {});
  }, []);

  const loadGps = useCallback(() => {
    adminAPI.getGpsConflicts().then(setGpsData).catch(() => {});
  }, []);

  const loadMethodologies = useCallback(() => {
    adminAPI.getMethodologies().then(setMethodologies).catch(() => {});
  }, []);

  const loadPagesAudit = useCallback((sector?: string) => {
    setPagesLoading(true);
    adminAPI
      .getPagesAudit(sector || undefined)
      .then((data) => {
        setPagesAudit(data);
        if (data.length === 1) setExpandedSector(data[0].code);
      })
      .catch(() => {})
      .finally(() => setPagesLoading(false));
  }, []);

  useEffect(() => {
    if (user && user.is_admin) {
      adminAPI
        .getStats()
        .then(setStats)
        .catch((e) => setError(e.message));
      adminAPI
        .getUsers()
        .then((data) => { setUsers(data); setUsersError(null); })
        .catch((e) => setUsersError(e.message));
      loadPrompts();
      loadGps();
      loadMethodologies();
      adminAPI.getSectors().then(setSectors).catch(() => {});
      loadPagesAudit();
      freshnessAPI.get().then(setFreshness).catch(() => {});
    }
  }, [user, loadPrompts, loadGps, loadMethodologies, loadPagesAudit]);

  const handleDeletePage = async (competitorId: number, platform: string, pageId?: string) => {
    await adminAPI.deletePage(competitorId, platform, pageId);
    loadPagesAudit(selectedSector || undefined);
  };

  const handleUpdateCompetitor = async (competitorId: number, field: string, value: string) => {
    await adminAPI.updateCompetitor(competitorId, { [field]: value || null });
    loadPagesAudit(selectedSector || undefined);
  };

  const reloadUsers = () => {
    adminAPI.getUsers().then((data) => { setUsers(data); setUsersError(null); }).catch((e) => setUsersError(e.message));
  };

  const handleToggleUser = async (userId: number, field: "is_active" | "is_admin", value: boolean) => {
    setSavingUser(userId);
    try {
      await adminAPI.updateUser(userId, { [field]: value });
      reloadUsers();
    } catch (e: any) {
      alert(e.message || "Erreur");
    } finally {
      setSavingUser(null);
    }
  };

  const handleSaveUser = async (userId: number) => {
    setSavingUser(userId);
    try {
      await adminAPI.updateUser(userId, editUserData);
      setEditingUser(null);
      reloadUsers();
    } catch (e: any) {
      alert(e.message || "Erreur");
    } finally {
      setSavingUser(null);
    }
  };

  const handleResetPassword = async (userId: number) => {
    if (newPassword.length < 6) { alert("Le mot de passe doit faire au moins 6 caracteres"); return; }
    setSavingUser(userId);
    try {
      await adminAPI.updateUser(userId, { password: newPassword });
      setResetPasswordUser(null);
      setNewPassword("");
    } catch (e: any) {
      alert(e.message || "Erreur");
    } finally {
      setSavingUser(null);
    }
  };

  const handleDeleteUser = async (userId: number, email: string) => {
    if (!confirm(`Supprimer l'utilisateur ${email} ? Cette action est irreversible.`)) return;
    setSavingUser(userId);
    try {
      await adminAPI.deleteUser(userId);
      reloadUsers();
    } catch (e: any) {
      alert(e.message || "Erreur");
    } finally {
      setSavingUser(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-6 w-6 border-2 border-violet-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!user || !user.is_admin) return null;

  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 text-white shadow-md">
          <Shield className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">Backoffice</h1>
          <p className="text-sm text-muted-foreground flex items-center gap-2">
            Administration de la plateforme
            {freshness && <FreshnessBadge timestamp={Object.values(freshness).filter(Boolean).sort().reverse()[0] || null} label="Dernière maj" />}
          </p>
        </div>
      </div>

      {!stats ? (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin h-6 w-6 border-2 border-violet-500 border-t-transparent rounded-full" />
        </div>
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            <StatCard icon={Store} label="Enseignes" value={stats.brands} />
            <StatCard icon={Target} label="Concurrents" value={stats.competitors} />
            <StatCard icon={Megaphone} label="Publicites" value={stats.data_volume.ads} />
            <StatCard
              icon={Instagram}
              label="Instagram"
              value={stats.data_volume.instagram_records}
            />
            <StatCard icon={Music} label="TikTok" value={stats.data_volume.tiktok_records} />
            <StatCard icon={Youtube} label="YouTube" value={stats.data_volume.youtube_records} />
            <StatCard icon={Smartphone} label="Apps" value={stats.data_volume.app_records} />
            <StatCard
              icon={MapPin}
              label="Magasins"
              value={stats.data_volume.store_locations}
            />
          </div>

          {/* ============= PAGES AUDIT SECTION ============= */}
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Layers className="h-4 w-4 text-indigo-500" />
                Audit des pages par verticale
              </h2>
              <div className="flex items-center gap-2">
                <select
                  className="text-xs rounded-lg border border-border bg-background px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={selectedSector}
                  onChange={(e) => {
                    setSelectedSector(e.target.value);
                    loadPagesAudit(e.target.value || undefined);
                    setExpandedSector(null);
                  }}
                >
                  <option value="">Toutes les verticales</option>
                  {sectors.map((s) => (
                    <option key={s.code} value={s.code}>
                      {s.name} ({s.competitors_count})
                    </option>
                  ))}
                </select>
                <button
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-violet-300 bg-violet-50 text-violet-700 hover:bg-violet-100 disabled:opacity-50"
                  disabled={reEnrichingAll}
                  onClick={async () => {
                    if (!confirm("Re-enrichir tous les concurrents ? Cela peut prendre plusieurs minutes.")) return;
                    setReEnrichingAll(true);
                    try {
                      const res = await adminAPI.reEnrichAll();
                      alert(res.message);
                    } catch (e: any) {
                      alert(e.message || "Erreur");
                    } finally {
                      setReEnrichingAll(false);
                    }
                  }}
                >
                  <Sparkles className="h-3 w-3" />
                  {reEnrichingAll ? "Enrichissement..." : "Re-enrichir tout"}
                </button>
                <button
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-50"
                  disabled={deduplicating}
                  onClick={async () => {
                    if (!confirm("Fusionner les concurrents en doublon ? Cette action est irreversible.")) return;
                    setDeduplicating(true);
                    try {
                      const res = await adminAPI.deduplicate();
                      alert(res.message);
                      loadPagesAudit(selectedSector || undefined);
                    } catch (e: any) {
                      alert(e.message || "Erreur");
                    } finally {
                      setDeduplicating(false);
                    }
                  }}
                >
                  <Layers className="h-3 w-3" />
                  {deduplicating ? "..." : "Dedupliquer"}
                </button>
              </div>
            </div>

            {pagesLoading ? (
              <div className="flex items-center justify-center h-20">
                <div className="animate-spin h-5 w-5 border-2 border-indigo-500 border-t-transparent rounded-full" />
              </div>
            ) : pagesAudit.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">Aucun concurrent trouve</p>
            ) : (
              <div className="space-y-2">
                {pagesAudit.map((sector) => {
                  const isOpen = expandedSector === sector.code;
                  const totalPages = sector.competitors.reduce((sum, c) => {
                    return sum + c.platforms.facebook.total_pages
                      + (c.platforms.instagram.configured ? 1 : 0)
                      + (c.platforms.tiktok.configured ? 1 : 0)
                      + (c.platforms.youtube.configured ? 1 : 0)
                      + (c.platforms.playstore.configured ? 1 : 0)
                      + (c.platforms.appstore.configured ? 1 : 0)
                      + (c.platforms.google.configured ? 1 : 0);
                  }, 0);

                  return (
                    <div key={sector.code} className="rounded-lg border border-border overflow-hidden">
                      <button
                        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors"
                        onClick={() => setExpandedSector(isOpen ? null : sector.code)}
                      >
                        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                          <Store className="h-4 w-4 text-indigo-500" />
                          {sector.name}
                          <span className="text-[10px] text-muted-foreground font-normal">
                            {sector.competitors.length} marques / {totalPages} pages
                          </span>
                        </span>
                        <ChevronDown
                          className={`h-4 w-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
                        />
                      </button>
                      {isOpen && (
                        <div className="border-t border-border">
                          {sector.competitors.map((comp) => (
                            <CompetitorPagesRow
                              key={comp.id}
                              comp={comp}
                              onDelete={handleDeletePage}
                              onUpdate={handleUpdateCompetitor}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ============= DATA HEALTH SECTION ============= */}
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Activity className="h-4 w-4 text-emerald-500" />
                Santé des données
              </h2>
              <button
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                disabled={healthLoading}
                onClick={async () => {
                  setHealthLoading(true);
                  try {
                    const res = await adminAPI.getDataHealth();
                    setDataHealth(res);
                  } catch (e: any) {
                    alert(e.message || "Erreur");
                  } finally {
                    setHealthLoading(false);
                  }
                }}
              >
                {healthLoading ? "Chargement..." : "Analyser"}
              </button>
            </div>

            {dataHealth && (
              <div className="space-y-3">
                {/* Coverage */}
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
                  {Object.entries(dataHealth.coverage as Record<string, { count: number; pct: number }>).map(([key, val]) => (
                    <div key={key} className="text-center rounded-lg bg-muted/30 p-2">
                      <div className={`text-lg font-bold ${val.pct >= 80 ? "text-emerald-600" : val.pct >= 50 ? "text-amber-600" : "text-red-600"}`}>{val.pct}%</div>
                      <div className="text-[10px] text-muted-foreground capitalize">{key}</div>
                    </div>
                  ))}
                </div>

                {/* Warnings */}
                {dataHealth.never_enriched.length > 0 && (
                  <div className="rounded-lg bg-red-50 border border-red-200 p-3">
                    <div className="text-xs font-semibold text-red-700 mb-1">Jamais enrichis ({dataHealth.never_enriched.length})</div>
                    <div className="flex flex-wrap gap-1">
                      {dataHealth.never_enriched.map((c: any) => (
                        <span key={c.id} className="text-[11px] bg-red-100 text-red-700 px-2 py-0.5 rounded-full">{c.name}</span>
                      ))}
                    </div>
                  </div>
                )}

                {dataHealth.stale.length > 0 && (
                  <div className="rounded-lg bg-amber-50 border border-amber-200 p-3">
                    <div className="text-xs font-semibold text-amber-700 mb-1">Données périmées &gt; 7j ({dataHealth.stale.length})</div>
                    <div className="flex flex-wrap gap-1">
                      {dataHealth.stale.map((c: any) => (
                        <span key={c.id} className="text-[11px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{c.name}</span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Health table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="px-2 py-1.5 font-medium">Concurrent</th>
                        <th className="px-2 py-1.5 font-medium text-center">Instagram</th>
                        <th className="px-2 py-1.5 font-medium text-center">TikTok</th>
                        <th className="px-2 py-1.5 font-medium text-center">YouTube</th>
                        <th className="px-2 py-1.5 font-medium text-center">Ads</th>
                        <th className="px-2 py-1.5 font-medium text-center">Play Store</th>
                        <th className="px-2 py-1.5 font-medium text-center">App Store</th>
                        <th className="px-2 py-1.5 font-medium text-center">Dernière maj</th>
                        <th className="px-2 py-1.5"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {dataHealth.report.map((r: any) => {
                        const dotColor = (ts: string | null) => {
                          if (!ts) return "bg-gray-300";
                          const h = (Date.now() - new Date(ts).getTime()) / 3600000;
                          return h < 24 ? "bg-emerald-500" : h < 72 ? "bg-amber-500" : "bg-red-500";
                        };
                        return (
                          <tr key={r.id} className="border-b border-border/30 hover:bg-muted/20">
                            <td className="px-2 py-1.5 font-medium text-foreground">{r.name}</td>
                            {["instagram", "tiktok", "youtube", "ads", "playstore", "appstore"].map((k) => (
                              <td key={k} className="px-2 py-1.5 text-center">
                                <span className={`inline-block h-2 w-2 rounded-full ${dotColor(r.sources?.[k])}`} />
                              </td>
                            ))}
                            <td className="px-2 py-1.5 text-center text-muted-foreground">
                              {r.latest ? new Date(r.latest).toLocaleDateString("fr-FR") : "—"}
                            </td>
                            <td className="px-2 py-1.5">
                              <button
                                className="text-violet-600 hover:text-violet-800 disabled:opacity-30"
                                disabled={reEnrichingId === r.id}
                                onClick={async () => {
                                  setReEnrichingId(r.id);
                                  try {
                                    await adminAPI.reEnrich(r.id);
                                    const res = await adminAPI.getDataHealth();
                                    setDataHealth(res);
                                  } catch {} finally { setReEnrichingId(null); }
                                }}
                                title="Re-enrichir"
                              >
                                <Sparkles className="h-3 w-3" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Scheduler */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              Scheduler
            </h2>
            <div className="flex items-center gap-4 text-sm mb-3">
              <span className="flex items-center gap-1.5">
                {stats.scheduler.running ? (
                  <CheckCircle className="h-4 w-4 text-green-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                {stats.scheduler.running ? "En cours" : "Arrete"}
              </span>
              <span className="text-muted-foreground">
                {stats.scheduler.enabled ? "Active" : "Desactive"}
              </span>
            </div>
            {stats.scheduler.jobs.length > 0 && (
              <div className="space-y-1.5">
                {stats.scheduler.jobs.map((job) => (
                  <div
                    key={job.id}
                    className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-2 text-xs"
                  >
                    <span className="font-medium text-foreground">{job.name}</span>
                    <span className="text-muted-foreground">
                      {job.next_run
                        ? new Date(job.next_run).toLocaleString("fr-FR")
                        : "Pas programme"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Prompts IA */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-500" />
              Prompts IA
            </h2>
            {prompts.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun prompt configure</p>
            ) : (
              <div className="space-y-3">
                {prompts.map((p) => (
                  <div key={p.key} className="rounded-lg border border-border p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <span className="text-sm font-medium text-foreground">{p.label}</span>
                        <span className="ml-2 text-[10px] text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded">{p.key}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="font-mono">{p.model_id}</span>
                        <span>|</span>
                        <span>{p.max_tokens} tokens</span>
                        {p.updated_at && (
                          <>
                            <span>|</span>
                            <span>{new Date(p.updated_at).toLocaleDateString("fr-FR")}</span>
                          </>
                        )}
                      </div>
                    </div>

                    {editingPrompt === p.key ? (
                      <div className="space-y-3 mt-3">
                        <textarea
                          className="w-full h-48 rounded-lg border border-border bg-muted/30 p-3 text-xs font-mono text-foreground resize-y focus:outline-none focus:ring-2 focus:ring-violet-500"
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                        />
                        <div className="flex items-center gap-3">
                          <div>
                            <label className="text-[10px] text-muted-foreground block mb-1">Modele</label>
                            <select
                              className="text-xs rounded border border-border bg-background px-2 py-1.5"
                              value={editModel}
                              onChange={(e) => setEditModel(e.target.value)}
                            >
                              <optgroup label="Google Gemini">
                                <option value="gemini-3-flash-preview">Gemini 3 Flash (recommande)</option>
                                <option value="gemini-3-pro-preview">Gemini 3 Pro</option>
                                <option value="gemini-3.1-pro-preview">Gemini 3.1 Pro</option>
                                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                                <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                              </optgroup>
                              <optgroup label="Mistral">
                                <option value="mistral-small-latest">Mistral Small 3.2</option>
                              </optgroup>
                              <optgroup label="Anthropic Claude">
                                <option value="claude-opus-4-6">Claude Opus 4.6</option>
                                <option value="claude-sonnet-4-5-20250929">Claude Sonnet 4.5</option>
                                <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5</option>
                              </optgroup>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-muted-foreground block mb-1">Max tokens</label>
                            <input
                              type="number"
                              className="w-24 text-xs rounded border border-border bg-background px-2 py-1.5"
                              value={editMaxTokens}
                              onChange={(e) => setEditMaxTokens(Number(e.target.value))}
                            />
                          </div>
                          <div className="flex-1" />
                          <button
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
                            disabled={savingPrompt}
                            onClick={async () => {
                              setSavingPrompt(true);
                              try {
                                await adminAPI.updatePrompt(p.key, {
                                  prompt_text: editText,
                                  model_id: editModel,
                                  max_tokens: editMaxTokens,
                                });
                                loadPrompts();
                                setEditingPrompt(null);
                              } catch (e) {
                                alert("Erreur lors de la sauvegarde");
                              } finally {
                                setSavingPrompt(false);
                              }
                            }}
                          >
                            <Save className="h-3 w-3" />
                            {savingPrompt ? "..." : "Sauvegarder"}
                          </button>
                          <button
                            className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-border text-muted-foreground hover:bg-muted"
                            onClick={() => setEditingPrompt(null)}
                          >
                            <X className="h-3 w-3" />
                            Annuler
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-2 mt-2">
                        <pre className="flex-1 text-[11px] text-muted-foreground font-mono whitespace-pre-wrap line-clamp-3 bg-muted/30 rounded p-2">
                          {p.prompt_text.slice(0, 200)}...
                        </pre>
                        <button
                          className="shrink-0 px-3 py-1.5 text-xs rounded-lg border border-border text-foreground hover:bg-muted"
                          onClick={() => {
                            setEditingPrompt(p.key);
                            setEditText(p.prompt_text);
                            setEditModel(p.model_id);
                            setEditMaxTokens(p.max_tokens);
                          }}
                        >
                          Modifier
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* GPS Conflicts */}
          <div className="rounded-xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground mb-1 flex items-center gap-2">
              <Navigation className="h-4 w-4 text-blue-500" />
              Verification GPS BANCO
            </h2>
            {gpsData && (
              <p className="text-xs text-muted-foreground mb-4">
                {gpsData.conflicts_count} conflit{gpsData.conflicts_count !== 1 ? "s" : ""} detecte{gpsData.conflicts_count !== 1 ? "s" : ""} sur {gpsData.total_stores} magasins (seuil : {gpsData.threshold_m}m)
              </p>
            )}
            {!gpsData ? (
              <div className="flex items-center justify-center h-20">
                <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
              </div>
            ) : gpsData.conflicts.length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-green-600">
                <CheckCircle className="h-4 w-4" />
                Aucun conflit GPS detecte
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-muted-foreground">
                      <th className="px-3 py-2 font-medium">Magasin</th>
                      <th className="px-3 py-2 font-medium">Ville</th>
                      <th className="px-3 py-2 font-medium text-center">Distance</th>
                      <th className="px-3 py-2 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gpsData.conflicts.map((c) => (
                      <tr key={c.store_id} className="border-b border-border/50 last:border-0">
                        <td className="px-3 py-2.5">
                          <span className="font-medium text-foreground text-xs">{c.store_name}</span>
                        </td>
                        <td className="px-3 py-2.5 text-xs text-muted-foreground">
                          {c.city} ({c.postal_code})
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                              c.distance_m > 500
                                ? "bg-red-50 text-red-700"
                                : c.distance_m > 100
                                ? "bg-amber-50 text-amber-700"
                                : "bg-green-50 text-green-700"
                            }`}
                          >
                            <AlertTriangle className="h-3 w-3" />
                            {c.distance_m}m
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          {c.gps_verified ? (
                            <span className="text-[11px] text-green-600 flex items-center gap-1 justify-end">
                              <CheckCircle className="h-3 w-3" /> Resolu
                            </span>
                          ) : (
                            <div className="flex items-center gap-1.5 justify-end">
                              <button
                                className="px-2 py-1 text-[11px] rounded border border-border text-foreground hover:bg-muted disabled:opacity-50"
                                disabled={resolvingId === c.store_id}
                                onClick={async () => {
                                  setResolvingId(c.store_id);
                                  try {
                                    await adminAPI.resolveGpsConflict(c.store_id, "store");
                                    loadGps();
                                  } finally {
                                    setResolvingId(null);
                                  }
                                }}
                              >
                                Garder ma position
                              </button>
                              <button
                                className="px-2 py-1 text-[11px] rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                                disabled={resolvingId === c.store_id}
                                onClick={async () => {
                                  setResolvingId(c.store_id);
                                  try {
                                    await adminAPI.resolveGpsConflict(c.store_id, "banco");
                                    loadGps();
                                  } finally {
                                    setResolvingId(null);
                                  }
                                }}
                              >
                                Utiliser BANCO
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Methodologies */}
          {methodologies.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5">
              <h2 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-indigo-500" />
                Methodologie d&apos;analyse
              </h2>
              <div className="space-y-2">
                {methodologies.map((mod) => {
                  const isOpen = openModule === mod.module;
                  const iconMap: Record<string, any> = {
                    Globe, Sparkles, Smartphone, Megaphone, MapPin,
                  };
                  const ModIcon = iconMap[mod.icon] || BookOpen;
                  const colorMap: Record<string, string> = {
                    Globe: "text-blue-500",
                    Sparkles: "text-teal-500",
                    Smartphone: "text-violet-500",
                    Megaphone: "text-amber-500",
                    MapPin: "text-emerald-500",
                  };
                  const iconColor = colorMap[mod.icon] || "text-gray-500";
                  return (
                    <div key={mod.module} className="rounded-lg border border-border overflow-hidden">
                      <button
                        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors"
                        onClick={() => setOpenModule(isOpen ? null : mod.module)}
                      >
                        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
                          <ModIcon className={`h-4 w-4 ${iconColor}`} />
                          {mod.module}
                          <span className="text-[10px] text-muted-foreground font-normal">({mod.fields.length} metriques)</span>
                        </span>
                        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
                      </button>
                      {isOpen && (
                        <div className="px-4 pb-4 space-y-3 border-t border-border pt-3">
                          {mod.fields.map((f) => (
                            <div key={f.key} className="rounded-lg bg-muted/30 px-4 py-3">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-semibold text-foreground">{f.label}</span>
                                <span className="text-[9px] text-muted-foreground font-mono bg-muted px-1 py-0.5 rounded">{f.key}</span>
                              </div>
                              <p className="text-[11px] text-muted-foreground leading-relaxed">{f.description}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Users table */}
          <div className="rounded-xl border border-border bg-card">
            <div className="px-5 py-4 border-b border-border">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <Users className="h-4 w-4 text-violet-500" />
                Utilisateurs ({users.length})
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="px-4 py-2.5 font-medium">Email</th>
                    <th className="px-4 py-2.5 font-medium">Nom</th>
                    <th className="px-4 py-2.5 font-medium">Enseigne</th>
                    <th className="px-4 py-2.5 font-medium text-center">Concurrents</th>
                    <th className="px-4 py-2.5 font-medium text-center">Actif</th>
                    <th className="px-4 py-2.5 font-medium text-center">Admin</th>
                    <th className="px-4 py-2.5 font-medium">Inscription</th>
                    <th className="px-4 py-2.5 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const isEditing = editingUser === u.id;
                    const isResettingPw = resetPasswordUser === u.id;
                    const isSelf = user?.id === u.id;
                    return (
                      <tr key={u.id} className="border-b border-border/50 last:border-0">
                        <td className="px-4 py-2.5">
                          {isEditing ? (
                            <input
                              className="w-full text-xs rounded border border-border bg-background px-2 py-1"
                              value={editUserData.email}
                              onChange={(e) => setEditUserData({ ...editUserData, email: e.target.value })}
                            />
                          ) : (
                            <span className="font-medium text-foreground text-xs">{u.email}</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          {isEditing ? (
                            <input
                              className="w-full text-xs rounded border border-border bg-background px-2 py-1"
                              value={editUserData.name}
                              onChange={(e) => setEditUserData({ ...editUserData, name: e.target.value })}
                            />
                          ) : (
                            <span className="text-muted-foreground text-xs">{u.name || "-"}</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5">
                          {u.brand_name ? (
                            <span className="inline-flex items-center rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700">
                              {u.brand_name}
                            </span>
                          ) : (
                            <span className="text-muted-foreground/50 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-center text-xs text-muted-foreground">
                          {u.competitors_count}
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <button
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors ${
                              u.is_active
                                ? "bg-green-50 text-green-700 hover:bg-green-100"
                                : "bg-red-50 text-red-600 hover:bg-red-100"
                            } ${isSelf ? "cursor-not-allowed opacity-60" : ""}`}
                            disabled={isSelf || savingUser === u.id}
                            onClick={() => handleToggleUser(u.id, "is_active", !u.is_active)}
                            title={isSelf ? "Impossible de modifier votre propre statut" : u.is_active ? "Desactiver" : "Activer"}
                          >
                            {u.is_active ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                            {u.is_active ? "Actif" : "Inactif"}
                          </button>
                        </td>
                        <td className="px-4 py-2.5 text-center">
                          <button
                            className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium transition-colors ${
                              u.is_admin
                                ? "bg-violet-50 text-violet-700 hover:bg-violet-100"
                                : "bg-muted text-muted-foreground hover:bg-muted/80"
                            } ${isSelf ? "cursor-not-allowed opacity-60" : ""}`}
                            disabled={isSelf || savingUser === u.id}
                            onClick={() => handleToggleUser(u.id, "is_admin", !u.is_admin)}
                            title={isSelf ? "Impossible de modifier votre propre role" : u.is_admin ? "Retirer admin" : "Rendre admin"}
                          >
                            <Shield className="h-3 w-3" />
                            {u.is_admin ? "Admin" : "User"}
                          </button>
                        </td>
                        <td className="px-4 py-2.5 text-[11px] text-muted-foreground">
                          {u.created_at
                            ? new Date(u.created_at).toLocaleDateString("fr-FR")
                            : "-"}
                        </td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-1 justify-end">
                            {isEditing ? (
                              <>
                                <button
                                  className="p-1 rounded bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
                                  disabled={savingUser === u.id}
                                  onClick={() => handleSaveUser(u.id)}
                                  title="Sauvegarder"
                                >
                                  <Save className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  className="p-1 rounded border border-border text-muted-foreground hover:bg-muted"
                                  onClick={() => setEditingUser(null)}
                                  title="Annuler"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              </>
                            ) : isResettingPw ? (
                              <div className="flex items-center gap-1">
                                <input
                                  type="password"
                                  className="w-28 text-[11px] rounded border border-border bg-background px-2 py-1"
                                  placeholder="Nouveau mdp"
                                  value={newPassword}
                                  onChange={(e) => setNewPassword(e.target.value)}
                                />
                                <button
                                  className="p-1 rounded bg-violet-600 text-white hover:bg-violet-700 disabled:opacity-50"
                                  disabled={savingUser === u.id}
                                  onClick={() => handleResetPassword(u.id)}
                                  title="Valider"
                                >
                                  <Save className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  className="p-1 rounded border border-border text-muted-foreground hover:bg-muted"
                                  onClick={() => { setResetPasswordUser(null); setNewPassword(""); }}
                                  title="Annuler"
                                >
                                  <X className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            ) : (
                              <>
                                <button
                                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                                  onClick={() => { setEditingUser(u.id); setEditUserData({ name: u.name || "", email: u.email }); }}
                                  title="Modifier nom/email"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                                  onClick={() => { setResetPasswordUser(u.id); setNewPassword(""); }}
                                  title="Reset mot de passe"
                                >
                                  <Key className="h-3.5 w-3.5" />
                                </button>
                                {!isSelf && (
                                  <button
                                    className="p-1 rounded hover:bg-red-50 text-muted-foreground hover:text-red-600 disabled:opacity-30"
                                    disabled={savingUser === u.id}
                                    onClick={() => handleDeleteUser(u.id, u.email)}
                                    title="Supprimer l'utilisateur"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" />
                                  </button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                        {usersError
                          ? <span className="text-red-500">Erreur : {usersError}</span>
                          : "Aucun utilisateur"}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
