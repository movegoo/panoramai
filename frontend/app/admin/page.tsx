"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { adminAPI, AdminStats, AdminUser, PromptTemplateData, GpsConflict, GpsConflictsResponse } from "@/lib/api";
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
  Globe,
} from "lucide-react";

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

  useEffect(() => {
    if (!loading && !user) {
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

  useEffect(() => {
    if (user) {
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
    }
  }, [user, loadPrompts, loadGps, loadMethodologies]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-6 w-6 border-2 border-violet-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!user) return null;

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
          <p className="text-sm text-muted-foreground">
            Statistiques de votre veille concurrentielle
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
                              <option value="claude-opus-4-6">Opus 4.6</option>
                              <option value="claude-sonnet-4-5-20250929">Sonnet 4.5</option>
                              <option value="claude-haiku-4-5-20251001">Haiku 4.5</option>
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
              <h2 className="text-sm font-semibold text-foreground">
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
                    <th className="px-4 py-2.5 font-medium text-center">Statut</th>
                    <th className="px-4 py-2.5 font-medium">Inscription</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-border/50 last:border-0">
                      <td className="px-4 py-2.5 font-medium text-foreground">{u.email}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{u.name || "-"}</td>
                      <td className="px-4 py-2.5">
                        {u.brand_name ? (
                          <span className="inline-flex items-center rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700">
                            {u.brand_name}
                          </span>
                        ) : (
                          <span className="text-muted-foreground/50">-</span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-center text-muted-foreground">
                        {u.competitors_count}
                      </td>
                      <td className="px-4 py-2.5 text-center">
                        <span
                          className={`inline-flex h-2 w-2 rounded-full ${
                            u.is_active ? "bg-green-500" : "bg-red-400"
                          }`}
                        />
                      </td>
                      <td className="px-4 py-2.5 text-xs text-muted-foreground">
                        {u.created_at
                          ? new Date(u.created_at).toLocaleDateString("fr-FR")
                          : "-"}
                      </td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
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
