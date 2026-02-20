import * as React from "react";
import { cn } from "../../lib/utils";

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { error?: boolean }>(
  ({ className, error, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-10 w-full rounded-lg border bg-slate-700 px-3 py-2 text-white placeholder-slate-500",
        "focus:outline-none focus:ring-2 focus:ring-emerald-500 border-slate-600",
        error && "border-red-500 focus:ring-red-500",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
export { Input };
