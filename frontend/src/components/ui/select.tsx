import * as React from "react";
import { cn } from "../../lib/utils";

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean;
}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, error, children, ...props }, ref) => (
    <select
      className={cn(
        "flex h-10 w-full rounded-lg border bg-slate-700 px-3 py-2 text-white transition-colors",
        "focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        error ? "border-red-500 focus:ring-red-500" : "border-slate-600",
        className
      )}
      ref={ref}
      {...props}
    >
      {children}
    </select>
  )
);
Select.displayName = "Select";

export { Select };
