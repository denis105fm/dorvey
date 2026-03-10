import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";
import { getAffiliateNetworkUrl } from "../utils/affiliateNetworks";

type DailyPoint = {
  date: string;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  ctr_percent: number;
  cr_percent: number;
};

export default function Analytics() {
  const [days, setDays] = useState(30);

  const { data: summary } = useQuery({
    queryKey: ["analytics-summary", days],
    queryFn: () => api.get("/analytics/summary", { params: { days } }).then((r) => r.data),
  });

  const { data: daily } = useQuery({
    queryKey: ["analytics-daily", days],
    queryFn: () => api.get("/analytics/daily", { params: { days } }).then((r) => r.data),
  });
  const { data: visitors } = useQuery({
    queryKey: ["analytics-visitors", days],
    queryFn: () => api.get("/analytics/visitors", { params: { days } }).then((r) => r.data),
  });
  const { data: emailLeads } = useQuery({
    queryKey: ["analytics-email-leads", days],
    queryFn: () => api.get("/analytics/email-leads", { params: { days } }).then((r) => r.data),
  });
  const { data: campaignStats } = useQuery({
    queryKey: ["analytics-campaigns", days],
    queryFn: () => api.get("/analytics/campaigns", { params: { days } }).then((r) => r.data),
  });
  const [affKeyword, setAffKeyword] = useState("");
  const [pushForm, setPushForm] = useState({ campaign_id: 0, doorway_id: 0 as number | undefined, title: "", body: "", url: "" });
  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: doorways } = useQuery({
    queryKey: ["doorways", pushForm.campaign_id],
    queryFn: () =>
      api.get("/doorways/", { params: pushForm.campaign_id ? { campaign_id: pushForm.campaign_id } : {} }).then((r) => r.data),
  });
  const sendPushMut = useMutation({
    mutationFn: (d: { campaign_id?: number; doorway_id?: number; title: string; body: string; url?: string }) =>
      api.post("/analytics/send-push", { ...d, campaign_id: d.campaign_id || undefined, doorway_id: d.doorway_id || undefined }).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`Отправлено: ${data.sent} из ${data.total}`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });
  const affRecMut = useMutation({
    mutationFn: (kw: string) =>
      api.post("/optimizer/affiliate-recommendations", { keyword: kw, language: "ru" }).then((r) => r.data),
  });

  const series: DailyPoint[] = daily?.series ?? [];

  const formatDate = (s: string) => {
    const d = new Date(s);
    return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
  };

  const exportVisitors = async (format: "csv" | "hashed_csv") => {
    try {
      const r = await api.get("/analytics/visitors/export", {
        params: { days, format },
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `visitors_${format}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Экспорт завершён");
    } catch {
      toast.error("Ошибка экспорта");
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Аналитика</h1>
      <div className="mb-4">
        <label className="text-slate-400 text-sm mr-2">Период:</label>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-white"
        >
          <option value={7}>7 дней</option>
          <option value={30}>30 дней</option>
          <option value={90}>90 дней</option>
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm">Показы</p>
          <p className="text-2xl font-bold text-white">{summary?.total_impressions ?? 0}</p>
        </div>
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm">Клики</p>
          <p className="text-2xl font-bold text-white">{summary?.total_clicks ?? 0}</p>
        </div>
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm">Конверсии</p>
          <p className="text-2xl font-bold text-white">{summary?.total_conversions ?? 0}</p>
        </div>
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
          <p className="text-slate-400 text-sm">Выручка</p>
          <p className="text-2xl font-bold text-emerald-400">
            {(summary?.total_revenue ?? 0).toFixed(2)}
          </p>
        </div>
      </div>
      <p className="text-slate-500 text-sm mb-6">
        CTR: {summary?.ctr_percent ?? 0}% · CR: {summary?.cr_percent ?? 0}%
      </p>

      {(visitors || emailLeads || campaigns) && (
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700 mb-6">
          <h2 className="text-lg font-medium text-white mb-3">База посетителей и Push</h2>
          <div className="flex flex-wrap gap-4 mb-4">
            {visitors && visitors.total >= 0 && (
              <p className="text-slate-400 text-sm">
                Уникальных посетителей: <span className="text-emerald-400 font-medium">{visitors.total}</span>
              </p>
            )}
            {emailLeads && emailLeads.total >= 0 && (
              <p className="text-slate-400 text-sm">
                Email-лидов: <span className="text-emerald-400 font-medium">{emailLeads.total}</span>
              </p>
            )}
            {visitors && visitors.total > 0 && (
              <div className="flex gap-2">
                <button
                  onClick={() => exportVisitors("csv")}
                  className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-white text-sm"
                >
                  Экспорт CSV
                </button>
                <button
                  onClick={() => exportVisitors("hashed_csv")}
                  className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-white text-sm"
                >
                  Экспорт (хеш)
                </button>
              </div>
            )}
          </div>
          {visitors && visitors.visitors?.length > 0 && (
            <div className="mt-4 overflow-x-auto">
              <p className="text-slate-500 text-xs mb-2">Первый/последний визит, с каких дорвеев заходил и активность — по всем событиям (и по старым захватам). Страна/устройство/IP — только у новых визитов.</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-400 border-b border-slate-600">
                    <th className="py-2 pr-2">ID посетителя</th>
                    <th className="py-2 pr-2">Событий</th>
                    <th className="py-2 pr-2">Первый визит</th>
                    <th className="py-2 pr-2">Последний визит</th>
                    <th className="py-2 pr-2">Страна</th>
                    <th className="py-2 pr-2">Устройство</th>
                    <th className="py-2 pr-2">IP</th>
                    <th className="py-2 pr-2">Кампания</th>
                    <th className="py-2 pr-2">Дорвей (посл.)</th>
                    <th className="py-2 pr-2">С дорвеев</th>
                    <th className="py-2 pr-2">Активность</th>
                  </tr>
                </thead>
                <tbody>
                  {visitors.visitors.slice(0, 50).map((v: { visitor_id: string; events: number; first_seen?: string; last_seen?: string; campaign_name?: string; doorway_path?: string; country?: string; device?: string; ip?: string; doorways_visited?: string[]; events_breakdown?: string }) => (
                    <tr key={v.visitor_id} className="border-b border-slate-700/50">
                      <td className="py-1.5 text-slate-300 font-mono text-xs">{String(v.visitor_id).slice(0, 16)}…</td>
                      <td className="py-1.5 text-slate-400">{v.events}</td>
                      <td className="py-1.5 text-slate-400">{v.first_seen ? new Date(v.first_seen).toLocaleString("ru-RU") : "—"}</td>
                      <td className="py-1.5 text-slate-400">{v.last_seen ? new Date(v.last_seen).toLocaleString("ru-RU") : "—"}</td>
                      <td className="py-1.5 text-slate-400">{v.country ?? "—"}</td>
                      <td className="py-1.5 text-slate-400">{v.device ?? "—"}</td>
                      <td className="py-1.5 text-slate-400 font-mono text-xs">{v.ip ?? "—"}</td>
                      <td className="py-1.5 text-slate-400">{v.campaign_name ?? "—"}</td>
                      <td className="py-1.5 text-slate-400">{v.doorway_path ?? "—"}</td>
                      <td className="py-1.5 text-slate-400 text-xs">{Array.isArray(v.doorways_visited) && v.doorways_visited.length ? v.doorways_visited.join(", ") : "—"}</td>
                      <td className="py-1.5 text-slate-400 text-xs">{v.events_breakdown ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {visitors.visitors.length > 50 && <p className="text-slate-500 text-xs mt-1">Показаны первые 50 из {visitors.visitors.length}</p>}
            </div>
          )}
          <div className="space-y-3 mt-3">
            <p className="text-slate-500 text-sm">Отправить push подписчикам (кампания или конкретный дорвей):</p>
            <div className="flex flex-wrap gap-2 items-end">
              <div>
                <label className="block text-slate-400 text-xs mb-1">Кампания</label>
                <select
                  value={pushForm.campaign_id}
                  onChange={(e) => setPushForm((f) => ({ ...f, campaign_id: +e.target.value, doorway_id: undefined }))}
                  className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                >
                  <option value={0}>—</option>
                  {campaigns?.map((c: { id: number; name: string }) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Дорвей (опц.)</label>
                <select
                  value={pushForm.doorway_id ?? 0}
                  onChange={(e) => setPushForm((f) => ({ ...f, doorway_id: +e.target.value || undefined }))}
                  className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                >
                  <option value={0}>{pushForm.campaign_id ? "Вся кампания" : "—"}</option>
                  {doorways?.map((d: { id: number; path: string }) => (
                    <option key={d.id} value={d.id}>#{d.id} {d.path}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Заголовок</label>
                <Input
                  value={pushForm.title}
                  onChange={(e) => setPushForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="Специальное предложение"
                  className="bg-slate-700 border-slate-600 w-48"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">Текст</label>
                <Input
                  value={pushForm.body}
                  onChange={(e) => setPushForm((f) => ({ ...f, body: e.target.value }))}
                  placeholder="Оформите заявку со скидкой"
                  className="bg-slate-700 border-slate-600 w-56"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-xs mb-1">URL (опц.)</label>
                <Input
                  value={pushForm.url}
                  onChange={(e) => setPushForm((f) => ({ ...f, url: e.target.value }))}
                  placeholder="/"
                  className="bg-slate-700 border-slate-600 w-40"
                />
              </div>
              <Button
                onClick={() =>
                  sendPushMut.mutate({
                    campaign_id: pushForm.campaign_id || undefined,
                    doorway_id: pushForm.doorway_id || undefined,
                    title: pushForm.title,
                    body: pushForm.body,
                    url: pushForm.url || undefined,
                  })
                }
                disabled={(!pushForm.campaign_id && !pushForm.doorway_id) || !pushForm.title.trim() || sendPushMut.isPending}
              >
                {sendPushMut.isPending ? "Отправка…" : "Отправить push"}
              </Button>
            </div>
          </div>
          <p className="text-slate-500 text-sm mt-3">
            <Link to="/push-ads" className="text-emerald-400 hover:underline">Перейти в конструктор push-рекламы →</Link>
          </p>
        </div>
      )}

      {emailLeads && emailLeads.leads?.length > 0 && (
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700 mb-6">
          <h2 className="text-lg font-medium text-white mb-3">Email-лиды</h2>
          <div className="overflow-x-auto max-h-48 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-600 text-slate-400 text-left">
                  <th className="py-2 pr-4">Email</th>
                  <th className="py-2 pr-4">Дата</th>
                </tr>
              </thead>
              <tbody>
                {emailLeads.leads.map((l: { id: number; email: string; created_at: string }) => (
                  <tr key={l.id} className="border-b border-slate-700/50">
                    <td className="py-2 text-white">{l.email}</td>
                    <td className="py-2 text-slate-400">{l.created_at ? formatDate(l.created_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {campaignStats?.campaigns?.length > 0 && (
        <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700 mb-8">
          <h2 className="text-lg font-medium text-white mb-4">Сводка по кампаниям</h2>
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

      <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700 mb-8">
        <h2 className="text-lg font-medium text-white mb-3">Партнёрки для ниши</h2>
        <p className="text-slate-400 text-sm mb-3">Ключевое слово → AI порекомендует подходящие партнёрские сети</p>
        <div className="flex gap-2 mb-3">
          <Input
            value={affKeyword}
            onChange={(e) => setAffKeyword(e.target.value)}
            placeholder="займ онлайн, кредит наличными..."
            className="bg-slate-700 border-slate-600 max-w-xs"
            onKeyDown={(e) => e.key === "Enter" && affRecMut.mutate(affKeyword)}
          />
          <Button onClick={() => affRecMut.mutate(affKeyword)} disabled={!affKeyword.trim() || affRecMut.isPending}>
            {affRecMut.isPending ? "..." : "Подобрать"}
          </Button>
        </div>
        {affRecMut.data?.recommendations?.length > 0 && (
          <ul className="space-y-2 mt-2">
            {affRecMut.data.recommendations.map((r: { network: string; name?: string; why: string }, i: number) => {
              const url = getAffiliateNetworkUrl(r.network);
              const title = r.name || r.network;
              return (
                <li key={i} className="p-3 bg-slate-700/50 rounded-lg text-sm">
                  {url ? (
                    <a href={url} target="_blank" rel="noopener noreferrer" className="text-emerald-400 font-medium hover:underline">
                      {title}
                    </a>
                  ) : (
                    <span className="text-emerald-400 font-medium">{title}</span>
                  )}
                  <span className="text-slate-400 ml-2">— {r.why}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {series.length > 0 && (
        <div className="space-y-6 mb-8">
          <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
            <h2 className="text-lg font-medium text-white mb-4">Показы и клики по дням</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" tickFormatter={formatDate} stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => (v >= 1000 ? `${v / 1000}k` : v)} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #475569" }}
                    labelFormatter={(label) => formatDate(label)}
                    formatter={(value: number | undefined) => [(value ?? 0).toLocaleString(), ""]}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="impressions" name="Показы" stroke="#22c55e" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="clicks" name="Клики" stroke="#3b82f6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
            <h2 className="text-lg font-medium text-white mb-4">Конверсии и выручка по дням</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" tickFormatter={formatDate} stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} yAxisId="L" />
                  <YAxis orientation="right" stroke="#94a3b8" fontSize={12} yAxisId="R" tickFormatter={(v) => `${v} ₽`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #475569" }}
                    labelFormatter={(label) => formatDate(label)}
                    formatter={(value: number | undefined, name: string | undefined) => [
                      name === "revenue" ? `${(value ?? 0).toFixed(2)} ₽` : (value ?? 0).toLocaleString(),
                      name === "conversions" ? "Конверсии" : "Выручка",
                    ]}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Legend />
                  <Line yAxisId="L" type="monotone" dataKey="conversions" name="Конверсии" stroke="#a78bfa" strokeWidth={2} dot={false} />
                  <Line yAxisId="R" type="monotone" dataKey="revenue" name="Выручка" stroke="#f59e0b" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-slate-800/80 rounded-xl p-5 border border-slate-700">
            <h2 className="text-lg font-medium text-white mb-4">CR % по дням</h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={series} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" tickFormatter={formatDate} stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickFormatter={(v) => `${v}%`} domain={[0, "auto"]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #475569" }}
                    labelFormatter={(label) => formatDate(label)}
                    formatter={(value: number | undefined) => [`${value ?? 0}%`, "CR"]}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="cr_percent" name="CR %" stroke="#06b6d4" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
        <h2 className="text-lg font-medium text-white mb-2">Postback URL</h2>
        <p className="text-slate-400 text-sm mb-2">
          Укажите в партнёрской сети URL для приёма конверсий. sub_id = doorway_id, payout = сумма.
        </p>
        <code className="block p-3 bg-slate-900 rounded text-emerald-400 text-sm overflow-x-auto">
          {typeof window !== "undefined"
            ? `${window.location.origin.replace(":5173", ":8000")}/api/analytics/postback?sub_id={doorway_id}&payout={payout}`
            : "https://your-api.com/api/analytics/postback?sub_id={doorway_id}&payout={payout}"}
        </code>
      </div>
    </div>
  );
}
