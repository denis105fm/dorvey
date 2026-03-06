import { Link, useLocation } from "react-router-dom";
import { ChevronRight } from "lucide-react";

const LABELS: Record<string, string> = {
  "/": "Дашборд",
  campaigns: "Кампании",
  doorways: "Дорвеи",
  templates: "Шаблоны",
  keywords: "Ключевые слова",
  analytics: "Аналитика",
  recommendations: "Рекомендации по офферам",
  "push-ads": "Push-реклама",
  servers: "Серверы",
  monitoring: "Мониторинг VPS",
  domains: "Домены",
  offers: "Офферы",
  seo: "SEO",
  settings: "Настройки",
  users: "Пользователи",
  instruction: "Инструкция",
};

export default function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  const items = segments.length ? segments : ["/"];

  return (
    <nav className="flex items-center gap-1 text-sm text-slate-500 mb-6">
      {items.map((seg, i) => {
        const path = items[0] === "/" ? "/" : "/" + items.slice(0, i + 1).join("/");
        const label = seg === "/" ? LABELS["/"] : LABELS[seg] ?? seg;
        const isLast = i === items.length - 1;

        return (
          <span key={path} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={14} className="text-slate-600" />}
            {isLast ? (
              <span className="text-slate-300 font-medium">{label}</span>
            ) : (
              <Link to={path} className="hover:text-white transition-colors">
                {label}
              </Link>
            )}
          </span>
        );
      })}
    </nav>
  );
}
