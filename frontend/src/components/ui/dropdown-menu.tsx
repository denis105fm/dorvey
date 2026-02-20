import * as React from "react";
import { cn } from "../../lib/utils";

interface DropdownMenuProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "left" | "right";
}

export function DropdownMenu({ trigger, children, align = "right" }: DropdownMenuProps) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) {
      document.addEventListener("click", handleClick);
      return () => document.removeEventListener("click", handleClick);
    }
  }, [open]);

  return (
    <div className="relative inline-block" ref={ref}>
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            "absolute z-50 mt-1 min-w-[160px] rounded-lg border border-slate-600 bg-slate-800 py-1 shadow-lg",
            align === "right" ? "right-0" : "left-0"
          )}
          onClick={() => setOpen(false)}
        >
          {children}
        </div>
      )}
    </div>
  );
}

export function DropdownMenuItem({
  children,
  onClick,
  className,
  variant = "default",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  className?: string;
  variant?: "default" | "danger";
}) {
  return (
    <button
      type="button"
      onClick={() => {
        onClick?.();
      }}
      className={cn(
        "w-full px-3 py-2 text-left text-sm transition-colors",
        variant === "default" ? "text-slate-300 hover:bg-slate-700 hover:text-white" : "text-red-400 hover:bg-red-500/10 hover:text-red-300",
        className
      )}
    >
      {children}
    </button>
  );
}
