import { TrendingUp, TrendingDown, type LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  delta?: number;
  deltaLabel?: string;
  icon?: LucideIcon;
  iconColor?: string;
  sub?: string;
}

export function StatCard({ label, value, delta, deltaLabel, icon: Icon, iconColor, sub }: StatCardProps) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex items-center gap-3 mb-3">
        {Icon && (
          <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${iconColor || "bg-violet-100 text-violet-600"}`}>
            <Icon className="h-4 w-4" />
          </div>
        )}
        <span className="text-[13px] font-medium text-muted-foreground">{label}</span>
      </div>
      <p className="text-xl font-bold tracking-tight text-foreground">{value}</p>
      {(delta !== undefined || sub) && (
        <div className="flex items-center gap-2 mt-1">
          {delta !== undefined && delta !== 0 && (
            <span className={`inline-flex items-center gap-0.5 text-xs font-semibold ${delta > 0 ? "text-emerald-600" : "text-red-600"}`}>
              {delta > 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {delta > 0 ? "+" : ""}{delta}%
            </span>
          )}
          {deltaLabel && <span className="text-[11px] text-muted-foreground">{deltaLabel}</span>}
          {sub && <span className="text-[11px] text-muted-foreground">{sub}</span>}
        </div>
      )}
    </div>
  );
}
