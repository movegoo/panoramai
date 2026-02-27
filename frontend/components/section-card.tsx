import { type LucideIcon } from "lucide-react";

interface SectionCardProps {
  title?: string;
  icon?: LucideIcon;
  iconColor?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  noPadding?: boolean;
  className?: string;
}

export function SectionCard({ title, icon: Icon, iconColor, action, children, noPadding, className }: SectionCardProps) {
  return (
    <div className={`rounded-xl border bg-card ${noPadding ? "" : "p-5"} ${className || ""}`}>
      {(title || action) && (
        <div className={`flex items-center justify-between ${noPadding ? "px-5 pt-5" : ""} ${title ? "mb-4" : ""}`}>
          <div className="flex items-center gap-2.5">
            {Icon && (
              <div className={`flex h-8 w-8 items-center justify-center rounded-xl ${iconColor || "bg-violet-100 text-violet-600"}`}>
                <Icon className="h-4 w-4" />
              </div>
            )}
            {title && <h2 className="text-[14px] font-semibold text-foreground">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </div>
  );
}
