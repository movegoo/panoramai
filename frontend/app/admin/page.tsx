"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { adminAPI, AdminStats, AdminUser } from "@/lib/api";
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (user) {
      adminAPI
        .getStats()
        .then(setStats)
        .catch((e) => setError(e.message));
      adminAPI
        .getUsers()
        .then(setUsers)
        .catch(() => {});
    }
  }, [user]);

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
                        Aucun utilisateur
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
