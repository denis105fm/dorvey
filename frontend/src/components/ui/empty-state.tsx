import * as React from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "../../lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-12 px-6 text-center",
        className
      )}
    >
      <div className="rounded-full bg-slate-700/50 p-4 mb-4">
        <Icon className="text-slate-500" size={40} strokeWidth={1.5} />
      </div>
      <h3 className="text-lg font-medium text-slate-300 mb-1">{title}</h3>
      {description && <p className="text-slate-500 text-sm mb-4 max-w-sm">{description}</p>}
      {action && <div>{action}</div>}
    </div>
  );
}
