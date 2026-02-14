import { Outlet, Link, useLocation } from "react-router-dom";
import { LayoutDashboard, FolderOpen, FileText, Server, Globe, LogOut, LayoutTemplate, Search, BarChart2, Settings, DollarSign, Users, Link2 } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useWhitelabel } from "../hooks/useWhitelabel";

const nav = [
  { to: "/", icon: LayoutDashboard, label: "Дашборд" },
  { to: "/campaigns", icon: FolderOpen, label: "Кампании" },
  { to: "/doorways", icon: FileText, label: "Дорвеи" },
  { to: "/templates", icon: LayoutTemplate, label: "Шаблоны" },
  { to: "/keywords", icon: Search, label: "Ключевые слова" },
  { to: "/analytics", icon: BarChart2, label: "Аналитика" },
  { to: "/servers", icon: Server, label: "Серверы" },
  { to: "/domains", icon: Globe, label: "Домены" },
  { to: "/offers", icon: DollarSign, label: "Офферы" },
  { to: "/seo", icon: Link2, label: "SEO" },
  { to: "/settings", icon: Settings, label: "Настройки" },
  { to: "/users", icon: Users, label: "Пользователи" },
];

export default function Layout() {
  const location = useLocation();
  const { logout } = useAuth();
  const { brandName, logoUrl, primaryColor } = useWhitelabel();
  const isActive = (to: string) =>
    location.pathname === to || (to !== "/" && location.pathname.startsWith(to));

  return (
    <div className="min-h-screen flex bg-slate-900">
      <aside className="w-64 border-r border-slate-700 bg-slate-800/50 flex flex-col">
        <div className="p-6 border-b border-slate-700">
          <Link to="/" className="flex items-center gap-2 text-xl font-bold" style={{ color: primaryColor }}>
            {logoUrl ? <img src={logoUrl} alt="" className="h-8 w-auto object-contain" /> : null}
            {brandName}
          </Link>
        </div>
        <nav className="flex-1 p-3 space-y-0.5">
          {nav.map(({ to, icon: Icon, label }) => (
            <Link
              key={to}
              to={to}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive(to) ? "opacity-90" : "text-slate-400 hover:text-slate-200 hover:bg-slate-700/50"
              }`}
              style={isActive(to) ? { backgroundColor: `${primaryColor}20`, color: primaryColor } : {}}
            >
              <Icon size={20} />
              {label}
            </Link>
          ))}
        </nav>
        <div className="p-3 border-t border-slate-700">
          <button
            onClick={logout}
            className="flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm text-slate-400 hover:text-red-400 hover:bg-slate-700/50 transition-colors"
          >
            <LogOut size={20} />
            Выйти
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-8">
        <Outlet />
      </main>
    </div>
  );
}
