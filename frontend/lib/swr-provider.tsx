"use client";

import { useMemo } from "react";
import { SWRConfig } from "swr";

/**
 * localStorage-backed SWR cache.
 * On page load, SWR reads from localStorage → instant render with last-known data.
 * On fetch, SWR writes back → always up to date for next visit.
 */
function localStorageProvider() {
  const STORAGE_KEY = "swr-cache";
  // Load persisted cache into a Map
  let stored: [string, any][] = [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) stored = JSON.parse(raw);
  } catch {}
  const map = new Map<string, any>(stored);

  // Persist on page unload
  if (typeof window !== "undefined") {
    window.addEventListener("beforeunload", () => {
      try {
        // Only persist api: keys (skip internal SWR keys), limit size
        const entries = Array.from(map.entries()).filter(([k]) => k.startsWith("api:"));
        localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
      } catch {}
    });
  }

  return map;
}

export function SWRProvider({ children }: { children: React.ReactNode }) {
  const provider = useMemo(() => localStorageProvider, []);
  return (
    <SWRConfig
      value={{
        provider,
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        dedupingInterval: 60_000,
        keepPreviousData: true,
        errorRetryCount: 1,
      }}
    >
      {children}
    </SWRConfig>
  );
}
