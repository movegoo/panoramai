"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { exportCSV, exportXLSX, ExportColumn } from "@/lib/export";

interface ExportMenuProps {
  data: Record<string, any>[];
  columns: ExportColumn[];
  filename: string;
  variant?: "default" | "dark";
}

export function ExportMenu({ data, columns, filename, variant = "default" }: ExportMenuProps) {
  const [open, setOpen] = useState(false);

  if (!data || data.length === 0) return null;

  const dark = variant === "dark";

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors ${
          dark
            ? "border-white/20 text-white/60 hover:text-white hover:bg-white/10"
            : "bg-white hover:bg-muted/50 text-muted-foreground hover:text-foreground"
        }`}
      >
        <Download className="h-3.5 w-3.5" />
        Exporter
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className={`absolute right-0 top-full mt-1 rounded-lg border shadow-lg z-50 py-1 min-w-[120px] ${
            dark ? "bg-slate-800 border-white/20" : "bg-white"
          }`}>
            <button
              onClick={() => { exportCSV(data, columns, filename); setOpen(false); }}
              className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                dark ? "text-white/70 hover:bg-white/10" : "hover:bg-muted/50"
              }`}
            >
              CSV
            </button>
            <button
              onClick={() => { exportXLSX(data, columns, filename); setOpen(false); }}
              className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                dark ? "text-white/70 hover:bg-white/10" : "hover:bg-muted/50"
              }`}
            >
              Excel (XLSX)
            </button>
          </div>
        </>
      )}
    </div>
  );
}
