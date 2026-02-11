"use client";

import FranceMap from "@/components/map/FranceMap";
import { Map } from "lucide-react";

export default function GeoPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-100 to-indigo-100 border border-violet-200/50">
          <Map className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">Carte & Zones</h1>
          <p className="text-[13px] text-muted-foreground">
            Analysez les zones de chalandise avec donn&eacute;es INSEE et loyers
          </p>
        </div>
      </div>

      <FranceMap />
    </div>
  );
}
