"use client";

import Link from "next/link";
import { Lock, ArrowLeft } from "lucide-react";
import { useFeatureAccess } from "@/lib/use-features";

export function PageGate({
  page,
  children,
}: {
  page: string;
  children: React.ReactNode;
}) {
  const { canPage } = useFeatureAccess();

  if (canPage(page)) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4 text-center max-w-md px-6">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
          <Lock className="h-8 w-8 text-muted-foreground" />
        </div>
        <h2 className="text-xl font-semibold text-foreground">
          Module non disponible
        </h2>
        <p className="text-sm text-muted-foreground">
          Ce module n&apos;est pas inclus dans votre abonnement. Contactez votre administrateur pour activer l&apos;acces.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Retour au dashboard
        </Link>
      </div>
    </div>
  );
}
