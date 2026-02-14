import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { FolderOpen, FileText, Server, Globe, TrendingUp, MousePointer, DollarSign } from "lucide-react";

export default function Dashboard() {
  const { data: summary } = useQuery({
    queryKey: ["analytics-summary"],
    queryFn: () => api.get("/analytics/summary", { params: { days: 30 } }).then((r) => r.data),
  });
  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: doorways } = useQuery({
    queryKey: ["doorways"],
    queryFn: () => api.get("/doorways/").then((r) => r.data),
  });
  const { data: servers } = useQuery({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then((r) => r.data),
  });
  const { data: domains } = useQuery({
    queryKey: ["domains"],
    queryFn: () => api.get("/domains/").then((r) => r.data),
  });
  const { data: anomalies } = useQuery({
    queryKey: ["anomalies"],
    queryFn: () => api.get("/optimizer/anomalies?days=14").then((r) => r.data),
  });

  const cards = [
    { label: "Кампании", value: campaigns?.length ?? 0, icon: FolderOpen, color: "emerald" },
    { label: "Дорвеи", value: doorways?.length ?? 0, icon: FileText, color: "blue" },
    { label: "Серверы", value: servers?.length ?? 0, icon: Server, color: "amber" },
    { label: "Домены", value: domains?.length ?? 0, icon: Globe, color: "violet" },
  ];
  const metrics = [
    { label: "Показы (30д)", value: summary?.total_impressions ?? 0, icon: TrendingUp, color: "sky" },
    { label: "Клики (30д)", value: summary?.total_clicks ?? 0, icon: MousePointer, color: "amber" },
    { label: "Конверсии (30д)", value: summary?.total_conversions ?? 0, icon: FileText, color: "emerald" },
    { label: "Выручка (30д)", value: (summary?.total_revenue ?? 0).toFixed(2), icon: DollarSign, color: "violet" },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Дашборд</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map(({ label, value, icon: Icon, color }) => (
          <div
            key={label}
            className="bg-slate-800/80 rounded-xl p-5 border border-slate-700 hover:border-slate-600 transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-sm">{label}</span>
              <Icon className={`text-${color}-400`} size={24} />
            </div>
            <p className="text-2xl font-bold text-white mt-2">{value}</p>
          </div>
        ))}
      </div>
      <h2 className="text-lg font-semibold text-white mt-8 mb-4">Метрики за 30 дней</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-sm">{label}</span>
              <Icon size={22} className="text-slate-500" />
            </div>
            <p className="text-2xl font-bold text-white mt-2">{value}</p>
          </div>
        ))}
      </div>
      {anomalies?.length > 0 && (
        <div className="mt-8 bg-amber-900/20 rounded-xl p-6 border border-amber-600/50">
          <h2 className="text-lg font-semibold text-amber-400 mb-3">⚠ Аномалии (последние 14 дней)</h2>
          <ul className="space-y-2 text-slate-300 text-sm">
            {anomalies.map((a: { doorway_id: number; type: string; message?: string }, i: number) => (
              <li key={i}>
                Дорвей #{a.doorway_id}: {a.type} {a.message ? `— ${a.message}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-8 bg-slate-800/80 rounded-xl p-6 border border-slate-700">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={20} className="text-emerald-400" />
          <h2 className="text-lg font-semibold text-white">Добро пожаловать в Dorvey</h2>
        </div>
        <p className="text-slate-400 text-sm leading-relaxed">
          Система умных дорвеев с AI-оптимизацией. Создавайте кампании, добавляйте серверы и домены, генерируйте
          дорвеи с помощью AI, деплойте и отслеживайте метрики. Полный план — в файле <code className="text-emerald-400">docs/MASTER_PLAN.md</code>.
        </p>
      </div>
    </div>
  );
}
