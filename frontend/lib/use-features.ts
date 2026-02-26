"use client";

import { useAuth } from "@/lib/auth";

export function useFeatureAccess() {
  const { user, currentAdvertiserId } = useAuth();
  const adv = user?.advertisers?.find((a) => a.id === currentAdvertiserId);
  const features = adv?.features;

  function can(key: string): boolean {
    if (!features) return true;
    const page = key.split(".")[0];
    if (page !== key && features[page] === false) return false;
    return features[key] !== false;
  }

  return { can, canPage: (p: string) => can(p), features };
}
