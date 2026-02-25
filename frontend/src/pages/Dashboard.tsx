import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import api from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Skeleton } from "../components/ui/skeleton";
import { FolderOpen, FileText, Server, Globe, TrendingUp, MousePointer, DollarSign, Plus, Zap, Sparkles, BarChart3 } from "lucide-react";

const CARD_COLORS: Record<string, string> = {
  emerald: "text-emerald-400",
  blue: "text-blue-400",
  amber: "text-amber-400",
  violet: "text-violet-400",
  sky: "text-sky-400",
};

export default function Dashboard() {
  const { data: summary, isLoading: summaryLoading } = useQuery({
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
  const { data: campaignStats } = useQuery({
    queryKey: ["analytics-campaigns", 30],
    queryFn: () => api.get("/analytics/campaigns", { params: { days: 30 } }).then((r) => r.data),
  });
  const { data: earlyDoorways } = useQuery({
    queryKey: ["analytics-early-doorways", 3, 20],
    queryFn: () => api.get("/analytics/early-doorways", { params: { days: 3, min_clicks: 20 } }).then((r) => r.data),
  });
  const [affKeyword, setAffKeyword] = useState("");
  const affRecMut = useMutation({
    mutationFn: (kw: string) =>
      api.post("/optimizer/affiliate-recommendations", { keyword: kw, language: "ru" }).then((r) => r.data),
  });

  const cards = [
    { label: "Кампании", value: campaigns?.length ?? 0, icon: FolderOpen, color: "emerald", to: "/campaigns" },
    { label: "Дорвеи", value: doorways?.length ?? 0, icon: FileText, color: "blue", to: "/doorways" },
    { label: "Серверы", value: servers?.length ?? 0, icon: Server, color: "amber", to: "/servers" },
    { label: "Домены", value: domains?.length ?? 0, icon: Globe, color: "violet", to: "/domains" },
  ];
  const metrics = [
    { label: "Показы (30д)", value: summary?.total_impressions ?? 0, icon: TrendingUp, color: "sky" },
    { label: "Клики (30д)", value: summary?.total_clicks ?? 0, icon: MousePointer, color: "amber" },
    { label: "CTR %", value: summary?.ctr_percent != null ? `${summary.ctr_percent}%` : "—", icon: MousePointer, color: "amber" },
    { label: "Конверсии (30д)", value: summary?.total_conversions ?? 0, icon: FileText, color: "emerald" },
    { label: "CR %", value: summary?.cr_percent != null ? `${summary.cr_percent}%` : "—", icon: FileText, color: "emerald" },
    { label: "Выручка (30д)", value: (summary?.total_revenue ?? 0).toFixed(2), icon: DollarSign, color: "violet" },
    {
      label: "Дорвеев с прибылью",
      value:
        summary?.doorways_with_traffic_count != null && summary.doorways_with_traffic_count > 0
          ? `${summary.profitable_doorways_percent ?? 0}% (${summary.profitable_doorways_count ?? 0} из ${summary.doorways_with_traffic_count})`
          : summary?.doorway_count
            ? "— (нет трафика)"
            : "—",
      icon: BarChart3,
      color: "emerald",
    },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Дашборд</h1>
        <div className="flex gap-2">
          <Link to="/doorways">
            <Button variant="secondary" size="sm" className="gap-1">
              <Zap size={16} />
              Сгенерировать
            </Button>
          </Link>
          <Link to="/campaigns">
            <Button variant="outline" size="sm" className="gap-1">
              <Plus size={16} />
              Кампания
            </Button>
          </Link>
        </div>
      </div>

      {earlyDoorways?.doorways?.length > 0 && (
        <Link to="/doorways" className="block mb-4">
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/15 transition-colors">
            <p className="text-amber-200 font-medium">
              Первые 48 ч: {earlyDoorways.doorways.length} дорвеев без конверсий за 3 дня
            </p>
            <p className="text-slate-400 text-sm mt-1">Перейти к списку →</p>
          </div>
        </Link>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map(({ label, value, icon: Icon, color, to }, i) => (
          <Link key={label} to={to} className="animate-fade-in-up" style={{ animationDelay: `${i * 50}ms` }}>
            <div className="card-volumetric p-5 cursor-pointer h-full">
              <div className="flex items-center justify-between">
                <span className="text-slate-400 text-sm">{label}</span>
                <Icon className={CARD_COLORS[color]} size={24} />
              </div>
              <p className="text-2xl font-bold text-white mt-2">{value}</p>
            </div>
          </Link>
        ))}
      </div>

      <h2 className="text-lg font-semibold text-white mt-8 mb-4 animate-fade-in-up" style={{ animationDelay: "150ms" }}>Метрики за 30 дней</h2>
      {summaryLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-6 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 rounded-2xl" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {metrics.map(({ label, value, icon: Icon, color }, i) => (
            <div key={label} className="card-volumetric p-5 animate-scale-in" style={{ animationDelay: `${180 + i * 40}ms` }}>
              <div className="flex items-center justify-between">
                <span className="text-slate-400 text-sm">{label}</span>
                <Icon className={CARD_COLORS[color]} size={22} />
              </div>
              <p className="text-2xl font-bold text-white mt-2">{value}</p>
            </div>
          ))}
        </div>
      )}

      {campaignStats?.campaigns?.length > 0 && (
        <div className="mt-8 card-volumetric animate-fade-in-up" style={{ animationDelay: "350ms" }}>
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Сводка по кампаниям (30 дней)</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-600 text-slate-400 text-left">
                  <th className="py-2 pr-4">Кампания</th>
                  <th className="py-2 pr-4">Показы</th>
                  <th className="py-2 pr-4">Клики</th>
                  <th className="py-2 pr-4">Конв.</th>
                  <th className="py-2 pr-4">CR %</th>
                  <th className="py-2 pr-4">Выручка</th>
                  <th className="py-2 pr-4">ROI/клик</th>
                  <th className="py-2">Дорвеев</th>
                </tr>
              </thead>
              <tbody>
                {campaignStats.campaigns.map((c: { campaign_id: number; name: string; impressions: number; clicks: number; conversions: number; cr_percent: number; revenue: number; roi_per_click: number; doorway_count: number }) => (
                  <tr key={c.campaign_id} className="border-b border-slate-700/50">
                    <td className="py-3 text-white">
                      <Link to="/campaigns" className="hover:text-emerald-400">{c.name}</Link>
                    </td>
                    <td className="py-3 text-slate-300">{c.impressions.toLocaleString()}</td>
                    <td className="py-3 text-slate-300">{c.clicks.toLocaleString()}</td>
                    <td className="py-3 text-slate-300">{c.conversions}</td>
                    <td className="py-3 text-slate-300">{c.cr_percent}%</td>
                    <td className="py-3 text-emerald-400 font-medium">{c.revenue.toFixed(2)}</td>
                    <td className="py-3 text-slate-300">{c.roi_per_click.toFixed(2)}</td>
                    <td className="py-3 text-slate-500">{c.doorway_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="mt-8 card-volumetric animate-fade-in-up" style={{ animationDelay: "400ms" }}>
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={20} className="text-amber-400" />
          <h2 className="text-lg font-semibold text-white">Партнёрки для ниши</h2>
        </div>
        <p className="text-slate-400 text-sm mb-3">
          Введите ключевое слово или нишу — AI порекомендует подходящие партнёрские сети
        </p>
        <div className="flex gap-2 mb-4">
          <Input
            value={affKeyword}
            onChange={(e) => setAffKeyword(e.target.value)}
            placeholder="займ онлайн, кредит наличными, ставки..."
            className="bg-slate-700 border-slate-600 max-w-md"
            onKeyDown={(e) => e.key === "Enter" && affRecMut.mutate(affKeyword)}
          />
          <Button
            onClick={() => affRecMut.mutate(affKeyword)}
            disabled={!affKeyword.trim() || affRecMut.isPending}
          >
            {affRecMut.isPending ? "..." : "Подобрать"}
          </Button>
        </div>
        {affRecMut.data?.recommendations?.length > 0 && (
          <div className="space-y-3">
            <p className="text-slate-500 text-sm">
              Ниша «{affRecMut.data.keyword}» — рекомендуемые партнёрки:
            </p>
            <ul className="space-y-2">
              {affRecMut.data.recommendations.map((r: { network: string; name?: string; why: string; priority: number }, i: number) => (
                <li key={i} className="flex gap-3 p-3 bg-slate-700/50 rounded-lg border border-slate-600/50">
                  <span className="text-emerald-400 font-medium shrink-0">#{i + 1}</span>
                  <div>
                    <p className="text-white font-medium">{r.name || r.network}</p>
                    <p className="text-slate-400 text-xs mt-0.5">{r.why}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
        {affRecMut.error && (
          <p className="text-red-400 text-sm">Ошибка: {String(affRecMut.error)}</p>
        )}
      </div>

      {anomalies?.length > 0 && (
        <div className="mt-8 bg-amber-900/20 rounded-xl p-6 border border-amber-600/50">
          <h2 className="text-lg font-semibold text-amber-400 mb-3">⚠ Аномалии (последние 14 дней)</h2>
          <ul className="space-y-2 text-slate-300 text-sm">
            {anomalies.map((a: { doorway_id: number; type: string; message?: string }, i: number) => (
              <li key={i}>
                <Link to="/doorways" className="text-amber-300 hover:text-amber-200 hover:underline">
                  Дорвей #{a.doorway_id}
                </Link>
                : {a.type} {a.message ? `— ${a.message}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-8 card-volumetric animate-fade-in-up" style={{ animationDelay: "450ms" }}>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={20} className="text-emerald-400" />
          <h2 className="text-lg font-semibold text-white">Добро пожаловать в Dorvey</h2>
        </div>
        <p className="text-slate-400 text-sm leading-relaxed">
          Система умных дорвеев с AI-оптимизацией. Создавайте кампании, добавляйте серверы и домены, генерируйте
          дорвеи с помощью AI, деплойте и отслеживайте метрики.
        </p>
      </div>
    </div>
  );
}
