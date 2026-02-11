"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  competitorsAPI,
  playstoreAPI,
  appstoreAPI,
  AppData,
} from "@/lib/api";
import { formatNumber, formatDate } from "@/lib/utils";
import {
  RefreshCw,
  ExternalLink,
  Star,
  Smartphone,
  BarChart3,
} from "lucide-react";

function StarRating({ rating }: { rating: number | null | undefined }) {
  if (!rating) return <span className="text-sm text-muted-foreground">&mdash;</span>;
  const full = Math.floor(rating);
  const partial = rating - full;
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex items-center gap-0.5">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="relative">
            <Star className="h-4 w-4 text-muted-foreground/20" />
            {i <= full && (
              <Star className="h-4 w-4 text-amber-400 fill-amber-400 absolute inset-0" />
            )}
            {i === full + 1 && partial > 0 && (
              <div
                className="absolute inset-0 overflow-hidden"
                style={{ width: `${partial * 100}%` }}
              >
                <Star className="h-4 w-4 text-amber-400 fill-amber-400" />
              </div>
            )}
          </div>
        ))}
      </div>
      <span className="text-sm font-bold tabular-nums">{rating.toFixed(1)}</span>
    </div>
  );
}

export default function AppsPage() {
  const [competitors, setCompetitors] = useState<any[]>([]);
  const [selectedCompetitor, setSelectedCompetitor] = useState<number | null>(
    null
  );
  const [selectedStore, setSelectedStore] = useState<"playstore" | "appstore">(
    "playstore"
  );
  const [appData, setAppData] = useState<AppData[]>([]);
  const [playstoreComparison, setPlaystoreComparison] = useState<any[]>([]);
  const [appstoreComparison, setAppstoreComparison] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    loadCompetitors();
    loadComparisons();
  }, []);

  useEffect(() => {
    if (selectedCompetitor) {
      loadAppData(selectedCompetitor, selectedStore);
    }
  }, [selectedCompetitor, selectedStore]);

  async function loadCompetitors() {
    try {
      const data = await competitorsAPI.list();
      const withApps = data.filter(
        (c) => c.playstore_app_id || c.appstore_app_id
      );
      setCompetitors(withApps);
      if (withApps.length > 0) {
        setSelectedCompetitor(withApps[0].id);
      }
    } catch (err) {
      console.error("Failed to load competitors:", err);
    } finally {
      setLoading(false);
    }
  }

  async function loadAppData(competitorId: number, store: string) {
    try {
      const api = store === "playstore" ? playstoreAPI : appstoreAPI;
      const data = await api.getData(competitorId);
      setAppData(data);
    } catch (err) {
      console.error("Failed to load app data:", err);
      setAppData([]);
    }
  }

  async function loadComparisons() {
    try {
      const [ps, as_] = await Promise.all([
        playstoreAPI.getComparison(),
        appstoreAPI.getComparison(),
      ]);
      setPlaystoreComparison(ps);
      setAppstoreComparison(as_);
    } catch (err) {
      console.error("Failed to load comparisons:", err);
    }
  }

  async function handleFetchData() {
    if (!selectedCompetitor) return;
    setFetching(true);
    try {
      const api = selectedStore === "playstore" ? playstoreAPI : appstoreAPI;
      await api.fetch(selectedCompetitor);
      await loadAppData(selectedCompetitor, selectedStore);
      await loadComparisons();
    } catch (err) {
      console.error("Failed to fetch data:", err);
      alert(err instanceof Error ? err.message : "Failed to fetch data");
    } finally {
      setFetching(false);
    }
  }

  const latestData = appData[0];
  const currentComparison =
    selectedStore === "playstore" ? playstoreComparison : appstoreComparison;

  // Sort comparison by rating
  const sortedComparison = [...currentComparison].sort(
    (a, b) => (b.rating || 0) - (a.rating || 0)
  );
  const maxReviews = Math.max(
    ...currentComparison.map((c) => c.reviews_count || 0),
    1
  );

  const selectedCompetitorData = competitors.find(
    (c) => c.id === selectedCompetitor
  );

  const storeUrl =
    selectedStore === "playstore" && selectedCompetitorData?.playstore_app_id
      ? `https://play.google.com/store/apps/details?id=${selectedCompetitorData.playstore_app_id}`
      : selectedStore === "appstore" && selectedCompetitorData?.appstore_app_id
      ? `https://apps.apple.com/app/id${selectedCompetitorData.appstore_app_id}`
      : null;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-2 border-violet-200 border-t-violet-600 animate-spin" />
          <span className="text-sm text-muted-foreground">Chargement des applications...</span>
        </div>
      </div>
    );
  }

  if (competitors.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
            <Smartphone className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Applications</h1>
            <p className="text-[13px] text-muted-foreground">Play Store & App Store</p>
          </div>
        </div>
        <div className="rounded-2xl border-2 border-dashed border-border bg-card/50 p-12 text-center">
          <div className="flex justify-center mb-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50">
              <Smartphone className="h-7 w-7 text-violet-400" />
            </div>
          </div>
          <h3 className="text-lg font-semibold text-foreground mb-1">Aucun concurrent configur&eacute;</h3>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Ajoutez des concurrents avec des IDs Play Store ou App Store.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
            <Smartphone className="h-5 w-5 text-violet-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground">Applications</h1>
            <p className="text-[13px] text-muted-foreground">
              Play Store & App Store
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleFetchData}
          disabled={fetching || !selectedCompetitor}
          className="gap-2"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${fetching ? "animate-spin" : ""}`}
          />
          Actualiser
        </Button>
      </div>

      {/* Store selector - pill style */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 p-1 rounded-full bg-muted/50 w-fit">
          <button
            onClick={() => setSelectedStore("playstore")}
            className={`relative px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
              selectedStore === "playstore"
                ? "text-white shadow-lg"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {selectedStore === "playstore" && (
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-green-500 via-blue-500 to-red-500" />
            )}
            <span className="relative">Play Store</span>
          </button>
          <button
            onClick={() => setSelectedStore("appstore")}
            className={`relative px-5 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
              selectedStore === "appstore"
                ? "text-white shadow-lg"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {selectedStore === "appstore" && (
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-blue-500 to-blue-600" />
            )}
            <span className="relative">App Store</span>
          </button>
        </div>

        {storeUrl && (
          <a
            href={storeUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <ExternalLink className="h-3 w-3" />
            Voir sur le store
          </a>
        )}
      </div>

      {/* Ratings comparison - all competitors */}
      {sortedComparison.length > 0 && (
        <div className="rounded-2xl bg-gradient-to-br from-indigo-950 via-[#1e1b4b] to-violet-950 text-white p-8 space-y-6 relative overflow-hidden">
          <div className="absolute -top-20 -right-20 h-60 w-60 rounded-full bg-violet-400/[0.05]" />
          <div className="absolute -bottom-10 -left-10 h-40 w-40 rounded-full bg-indigo-400/[0.04]" />
          <div className="flex items-center justify-between relative">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10 backdrop-blur-sm">
                <Star className="h-4 w-4 text-amber-400" />
              </div>
              <h3 className="text-[13px] font-semibold text-white">
                Classement{" "}
                {selectedStore === "playstore" ? "Play Store" : "App Store"}
              </h3>
            </div>
          </div>
          <div className="space-y-5">
            {sortedComparison.map((c, i) => {
              const reviewPct =
                maxReviews > 0
                  ? ((c.reviews_count || 0) / maxReviews) * 100
                  : 0;
              return (
                <div key={c.competitor_id} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span
                        className={`flex items-center justify-center h-6 w-6 rounded-full text-[11px] font-bold ${
                          i === 0
                            ? "bg-amber-400 text-slate-900"
                            : i === 1
                            ? "bg-slate-400 text-slate-900"
                            : "bg-slate-700 text-slate-300"
                        }`}
                      >
                        {i + 1}
                      </span>
                      <span className="font-medium">
                        {c.competitor_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-4">
                      {c.rating && (
                        <div className="flex items-center gap-1">
                          <Star className="h-3.5 w-3.5 text-amber-400 fill-amber-400" />
                          <span className="font-bold tabular-nums">
                            {c.rating.toFixed(1)}
                          </span>
                        </div>
                      )}
                      <span className="text-xs text-white/50 tabular-nums w-24 text-right">
                        {c.reviews_count
                          ? formatNumber(c.reviews_count)
                          : "0"}{" "}
                        avis
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 ml-9">
                    <div className="flex-1 h-1 rounded-full bg-white/10 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ease-out ${
                          i === 0
                            ? "bg-amber-400"
                            : i === 1
                            ? "bg-slate-400"
                            : "bg-slate-600"
                        }`}
                        style={{ width: `${reviewPct}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Competitor pills */}
      <div className="flex items-center gap-2 flex-wrap">
        {competitors.map((c) => {
          const hasStore =
            selectedStore === "playstore"
              ? c.playstore_app_id
              : c.appstore_app_id;
          return (
            <button
              key={c.id}
              onClick={() => setSelectedCompetitor(c.id)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                selectedCompetitor === c.id
                  ? "bg-foreground text-background shadow-lg scale-105"
                  : hasStore
                  ? "bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  : "bg-muted/50 text-muted-foreground/50 cursor-not-allowed"
              }`}
              disabled={!hasStore}
            >
              {c.name}
              {!hasStore && (
                <span className="ml-1 text-[10px] opacity-50">
                  (non config.)
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Selected competitor details */}
      {selectedCompetitorData &&
        ((selectedStore === "playstore" &&
          !selectedCompetitorData.playstore_app_id) ||
          (selectedStore === "appstore" &&
            !selectedCompetitorData.appstore_app_id)) ? (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="h-14 w-14 rounded-2xl bg-muted flex items-center justify-center mb-4">
            <Smartphone className="h-6 w-6 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium">
            Pas de{" "}
            {selectedStore === "playstore" ? "Play Store" : "App Store"}{" "}
            configure
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Editez ce concurrent pour ajouter un ID{" "}
            {selectedStore === "playstore" ? "Play Store" : "App Store"}.
          </p>
        </div>
      ) : (
        <>
          {/* Current stats strip */}
          {latestData && (
            <div className="grid grid-cols-4 gap-px rounded-xl bg-border overflow-hidden shadow-sm">
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">
                  Note
                </div>
                <div className="mt-2">
                  <StarRating rating={latestData.rating} />
                </div>
              </div>
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">
                  Avis
                </div>
                <div className="text-2xl font-bold mt-1 tabular-nums">
                  {latestData.reviews_count
                    ? formatNumber(latestData.reviews_count)
                    : "\u2014"}
                </div>
              </div>
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">
                  Telechargements
                </div>
                <div className="text-2xl font-bold mt-1 tabular-nums">
                  {latestData.downloads || "\u2014"}
                </div>
              </div>
              <div className="bg-card px-5 py-4">
                <div className="text-[11px] text-muted-foreground uppercase tracking-widest">
                  Version
                </div>
                <div className="text-2xl font-bold mt-1 tabular-nums">
                  {latestData.version || "\u2014"}
                </div>
              </div>
            </div>
          )}

          {/* Changelog */}
          {latestData?.changelog && (
            <div className="rounded-2xl border bg-card p-6 space-y-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
                  <RefreshCw className="h-4 w-4 text-blue-600" />
                </div>
                <h3 className="text-[13px] font-semibold text-foreground">
                  Dernier changelog
                </h3>
              </div>
              <p className="text-sm leading-relaxed text-foreground/80 whitespace-pre-wrap">
                {latestData.changelog}
              </p>
            </div>
          )}

          {/* History */}
          {appData.length > 0 && (
            <div className="rounded-2xl border bg-card overflow-hidden">
              <div className="px-5 py-3 bg-muted/20 border-b flex items-center gap-2.5">
                <div className="flex h-7 w-7 items-center justify-center rounded-md bg-slate-100">
                  <BarChart3 className="h-3.5 w-3.5 text-slate-600" />
                </div>
                <h3 className="text-[12px] font-semibold text-foreground">
                  Historique
                </h3>
              </div>
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                      Date
                    </th>
                    <th className="text-left text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                      Version
                    </th>
                    <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                      Note
                    </th>
                    <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                      Avis
                    </th>
                    <th className="text-right text-[11px] uppercase tracking-widest text-muted-foreground font-semibold px-5 py-3">
                      Downloads
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {appData.map((entry, i) => (
                    <tr
                      key={entry.id}
                      className={`border-t transition-colors hover:bg-muted/30 ${
                        i === 0 ? "bg-emerald-50/50 dark:bg-emerald-950/20" : ""
                      }`}
                    >
                      <td className="px-5 py-3 text-sm tabular-nums">
                        {formatDate(entry.recorded_at)}
                      </td>
                      <td className="px-5 py-3">
                        {entry.version ? (
                          <span className="inline-block text-xs font-medium bg-muted px-2 py-0.5 rounded">
                            v{entry.version}
                          </span>
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            &mdash;
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">
                        {entry.rating ? (
                          <div className="flex items-center justify-end gap-1">
                            <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                            <span className="text-sm font-medium tabular-nums">
                              {entry.rating.toFixed(1)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            &mdash;
                          </span>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right text-sm tabular-nums">
                        {entry.reviews_count
                          ? formatNumber(entry.reviews_count)
                          : "\u2014"}
                      </td>
                      <td className="px-5 py-3 text-right text-sm tabular-nums">
                        {entry.downloads || "\u2014"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
