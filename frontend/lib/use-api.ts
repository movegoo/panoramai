"use client";

import useSWR, { mutate as globalMutate } from "swr";
import { API_BASE, getCurrentAdvertiserId } from "./api";

/**
 * Generic SWR-based API hook with advertiser-scoped caching.
 * Cache key includes advertiser ID so switching advertiser invalidates cache.
 *
 * Usage:
 *   const { data, error, isLoading } = useAPI<MyType>("/watch/dashboard?period_days=30");
 *   const { data } = useAPI<Ad[]>("/facebook/ads/all", { revalidateOnMount: true });
 */
export function useAPI<T>(
  endpoint: string | null,
  options?: { revalidateOnMount?: boolean; refreshInterval?: number; fallbackData?: T }
) {
  const advId = typeof window !== "undefined" ? getCurrentAdvertiserId() : null;
  const cacheKey = endpoint ? `api:${advId}:${endpoint}` : null;

  return useSWR<T>(
    cacheKey,
    async () => {
      const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (advId) headers["X-Advertiser-Id"] = advId;

      const res = await fetch(`${API_BASE}${endpoint}`, { headers });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `API Error: ${res.status}`);
      }
      return res.json();
    },
    {
      revalidateOnMount: options?.revalidateOnMount ?? true,
      refreshInterval: options?.refreshInterval,
      fallbackData: options?.fallbackData,
    }
  );
}

/**
 * Invalidate all SWR cache entries for the current advertiser.
 * Call this when switching advertiser instead of window.location.reload().
 */
export function invalidateAllCache() {
  globalMutate(() => true, undefined, { revalidate: true });
}
