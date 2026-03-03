import * as React from "react";
import { createPortal } from "react-dom";
import { cn } from "../../lib/utils";

interface DropdownMenuProps {
  trigger: React.ReactNode;
  children: React.ReactNode;
  align?: "left" | "right";
}

export function DropdownMenu({ trigger, children, align = "right" }: DropdownMenuProps) {
  const [open, setOpen] = React.useState(false);
  const triggerRef = React.useRef<HTMLDivElement>(null);
  const panelRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) return;
      setOpen(false);
    }
    if (open) {
      document.addEventListener("click", handleClick);
      return () => document.removeEventListener("click", handleClick);
    }
  }, [open]);

  const position = React.useMemo(() => {
    if (!open || !triggerRef.current) return null;
    const rect = triggerRef.current.getBoundingClientRect();
    return {
      top: rect.bottom + 4,
      left: align === "right" ? rect.right : rect.left,
      transform: align === "right" ? "translateX(-100%)" : "none",
    };
  }, [open, align]);

  return (
    <div className="relative inline-block" ref={triggerRef}>
      <div onClick={() => setOpen((o) => !o)}>{trigger}</div>
      {open && position && typeof document !== "undefined" &&
        createPortal(
          <div
            ref={panelRef}
            className={cn(
              "fixed z-[100] mt-1 min-w-[160px] rounded-lg border border-slate-600 bg-slate-800 py-1 shadow-xl"
            )}
            style={{
              top: position.top,
              left: position.left,
              transform: position.transform,
            }}
            onClick={() => setOpen(false)}
          >
            {children}
          </div>,
          document.body
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
