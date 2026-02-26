"use client";
import { useState } from "react";
import { Sparkles, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { smartFilterAPI } from "@/lib/api";

interface SmartFilterProps {
  page: string;
  placeholder?: string;
  onFilter: (filters: Record<string, any>, interpretation: string) => void;
  onClear: () => void;
  resultCount?: number;
}

export function SmartFilter({ page, placeholder, onFilter, onClear, resultCount }: SmartFilterProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [interpretation, setInterpretation] = useState("");
  const [hasFilters, setHasFilters] = useState(false);

  const defaultPlaceholder = "Décrivez ce que vous cherchez... (ex: Leclerc, Instagram, score > 80)";

  const handleFilter = async () => {
    const q = query.trim();
    if (!q || loading) return;

    setLoading(true);
    try {
      const result = await smartFilterAPI.filter(q, page);
      if (result.filters) {
        setInterpretation(result.interpretation || "Filtres appliqués");
        setHasFilters(true);
        onFilter(result.filters, result.interpretation);
      }
    } catch {
      // Fallback to text search
      onFilter({ text_search: q }, `Recherche textuelle : ${q}`);
      setInterpretation(`Recherche textuelle : ${q}`);
      setHasFilters(true);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery("");
    setInterpretation("");
    setHasFilters(false);
    onClear();
  };

  return (
    <div className="relative">
      <div className="relative flex items-center gap-2">
        <div className="relative flex-1">
          <Sparkles className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-violet-500" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !loading) handleFilter(); }}
            placeholder={placeholder || defaultPlaceholder}
            className="w-full pl-10 pr-10 py-2.5 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-400 placeholder:text-muted-foreground/60"
          />
          {query && !loading && (
            <button onClick={handleClear} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
              <X className="h-4 w-4" />
            </button>
          )}
          {loading && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-violet-500 animate-spin" />
          )}
        </div>
        <Button
          variant="default"
          size="sm"
          onClick={handleFilter}
          disabled={loading || !query.trim()}
          className="gap-1.5 bg-violet-600 hover:bg-violet-700 text-white shrink-0"
        >
          <Sparkles className="h-3.5 w-3.5" />
          Filtrer
        </Button>
      </div>
      {hasFilters && interpretation && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-violet-100 text-violet-800 text-xs font-medium border border-violet-200">
            <Sparkles className="h-3 w-3" />
            {interpretation}
            <button onClick={handleClear} className="ml-1 hover:text-violet-950">
              <X className="h-3 w-3" />
            </button>
          </span>
          {resultCount !== undefined && (
            <span className="text-xs text-muted-foreground">
              {resultCount} résultat{resultCount !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
