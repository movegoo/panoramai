"use client";

import { SWRConfig } from "swr";

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        dedupingInterval: 60_000, // Dedupe identical requests within 60s
        keepPreviousData: true,   // Show stale data while revalidating
        errorRetryCount: 1,
      }}
    >
      {children}
    </SWRConfig>
  );
}
