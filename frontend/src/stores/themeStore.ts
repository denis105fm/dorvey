import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "dark" | "light";

interface ThemeStore {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: "dark",
      setTheme: (theme) => {
        set({ theme });
        document.documentElement.classList.toggle("light", theme === "light");
        document.documentElement.classList.toggle("dark", theme === "dark");
      },
      toggle: () =>
        set((s) => {
          const next = s.theme === "dark" ? "light" : "dark";
          document.documentElement.classList.toggle("light", next === "light");
          document.documentElement.classList.toggle("dark", next === "dark");
          return { theme: next };
        }),
    }),
    { name: "dorvey-theme" }
  )
);
