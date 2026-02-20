import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export function useKeyboardShortcuts() {
  const navigate = useNavigate();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.ctrlKey || e.metaKey) return;

      switch (e.key.toLowerCase()) {
        case "g":
          navigate("/doorways");
          break;
        case "d":
          navigate("/");
          break;
        case "escape":
          (document.activeElement as HTMLElement)?.blur();
          break;
        default:
          break;
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [navigate]);
}
