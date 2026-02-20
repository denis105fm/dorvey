import { useEffect } from "react";
import { useThemeStore } from "../stores/themeStore";

export default function ThemeInit() {
  const theme = useThemeStore((s) => s.theme);
  useEffect(() => {
    document.documentElement.classList.toggle("light", theme === "light");
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  return null;
}
