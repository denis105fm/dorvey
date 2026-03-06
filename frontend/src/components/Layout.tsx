import { Outlet, Link, useLocation } from "react-router-dom";
import { LayoutDashboard, FolderOpen, FileText, Server, Globe, LogOut, LayoutTemplate, Search, BarChart2, Settings, DollarSign, Users, Link2, Moon, Sun, Bell, TrendingUp, BookOpen, Activity } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useWhitelabel } from "../hooks/useWhitelabel";
import { useThemeStore } from "../stores/themeStore";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import Breadcrumbs from "./Breadcrumbs";
import FirstRunWizard from "./FirstRunWizard";

const navGroups = [
  {
    title: "Кампании",
    items: [
      { to: "/campaigns", icon: FolderOpen, label: "Кампании" },
      { to: "/doorways", icon: FileText, label: "Дорвеи" },
      { to: "/offers", icon: DollarSign, label: "Офферы" },
      { to: "/keywords", icon: Search, label: "Ключевые слова" },
    ],
  },
  {
    title: "Контент",
    items: [
      { to: "/templates", icon: LayoutTemplate, label: "Шаблоны" },
    ],
  },
  {
    title: "Инфраструктура",
    items: [
      { to: "/servers", icon: Server, label: "Серверы" },
      { to: "/monitoring", icon: Activity, label: "Мониторинг VPS" },
      { to: "/domains", icon: Globe, label: "Домены" },
    ],
  },
  {
    title: "Аналитика",
    items: [
      { to: "/analytics", icon: BarChart2, label: "Аналитика" },
      { to: "/recommendations", icon: TrendingUp, label: "Рекомендации по офферам" },
      { to: "/push-ads", icon: Bell, label: "Push-реклама" },
      { to: "/seo", icon: Link2, label: "SEO" },
    ],
  },
  {
    title: "Система",
    items: [
      { to: "/instruction", icon: BookOpen, label: "Инструкция" },
      { to: "/settings", icon: Settings, label: "Настройки" },
      { to: "/users", icon: Users, label: "Пользователи" },
    ],
  },
];

export default function Layout() {
  const location = useLocation();
  const { logout } = useAuth();
  const { brandName, logoUrl, primaryColor } = useWhitelabel();
  const { theme, toggle: toggleTheme } = useThemeStore();
  useKeyboardShortcuts();
  const isActive = (to: string) =>
    location.pathname === to || (to !== "/" && location.pathname.startsWith(to));

  return (
    <div className="min-h-screen flex bg-slate-900">
      <FirstRunWizard />
      <aside className="w-64 border-r border-slate-700 bg-slate-800/50 flex flex-col shrink-0">
        <div className="p-6 border-b border-slate-700">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold" style={{ color: primaryColor }}>
            {logoUrl ? <img src={logoUrl} alt="" className="h-8 w-auto object-contain" /> : null}
            {brandName}
          </Link>
        </div>
        <nav className="flex-1 overflow-y-auto p-3 space-y-4">
          <Link
            to="/"
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              location.pathname === "/" ? "opacity-90" : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
            }`}
            style={location.pathname === "/" ? { backgroundColor: `${primaryColor}20`, color: primaryColor } : {}}
          >
            <LayoutDashboard size={20} />
            Дашборд
          </Link>
          {navGroups.map((g) => (
            <div key={g.title}>
              <p className="px-3 py-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">{g.title}</p>
              <div className="space-y-0.5 mt-0.5">
                {g.items.map(({ to, icon: Icon, label }) => (
                  <Link
                    key={to}
                    to={to}
                    className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 ${
                      isActive(to) ? "opacity-90" : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 hover:translate-x-0.5"
                    }`}
                    style={isActive(to) ? { backgroundColor: `${primaryColor}20`, color: primaryColor } : {}}
                  >
                    <Icon size={20} />
                    {label}
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="p-3 border-t border-slate-700 space-y-0.5">
          <button
            onClick={toggleTheme}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 transition-colors"
          >
            {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
            {theme === "dark" ? "Светлая тема" : "Тёмная тема"}
          </button>
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:text-red-400 hover:bg-slate-700/50 transition-colors"
          >
            <LogOut size={20} />
            Выйти
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8 min-w-0">
        <Breadcrumbs />
        <div className="animate-fade-in-up" style={{ animationDuration: "0.3s" }}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
