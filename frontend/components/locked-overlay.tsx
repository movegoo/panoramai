"use client";

import { Lock } from "lucide-react";
import { useFeatureAccess } from "@/lib/use-features";

export function FeatureGate({
  feature,
  children,
}: {
  feature: string;
  children: React.ReactNode;
}) {
  const { can } = useFeatureAccess();

  if (can(feature)) {
    return <>{children}</>;
  }

  return (
    <div className="relative">
      <div className="pointer-events-none select-none blur-sm opacity-40">
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-background/30 backdrop-blur-[2px] rounded-xl">
        <div className="flex flex-col items-center gap-2 text-center px-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
            <Lock className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-muted-foreground">Module verrouille</p>
        </div>
      </div>
    </div>
  );
}
