import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Server as ServerIcon, Cpu, HardDrive, MemoryStick, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

type Server = { id: number; name: string; host: string; port: number; user: string };
type MetricPoint = {
  created_at: string;
  load_1: number | null;
  load_5: number | null;
  load_15: number | null;
  mem_total_kb: number | null;
  mem_available_kb: number | null;
  disk_total_kb: number | null;
  disk_used_kb: number | null;
  nproc: number | null;
};
type MetricsResponse = { server_id: number; period: string; metrics: MetricPoint[] };

function formatTime(s: string) {
  try {
    const d = new Date(s);
    return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return s;
  }
}

function ServerMonitorCard({ server, period }: { server: Server; period: string }) {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["server-metrics", server.id, period],
    queryFn: () =>
      api.get<MetricsResponse>(`/servers/${server.id}/metrics`, { params: { period } }).then((r) => r.data),
    refetchInterval: 2 * 60 * 1000,
  });

  const collectNowMut = useMutation({
    mutationFn: () => api.post(`/servers/${server.id}/metrics/collect`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["server-metrics", server.id, period] });
      toast.success("Метрики обновлены");
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => {
      toast.error(e?.response?.data?.detail ?? "Не удалось собрать метрики (SSH)");
    },
  });

  const metrics = data?.metrics ?? [];
  const last = metrics.length ? metrics[metrics.length - 1] : null;

  const memUsedPct =
    last && last.mem_total_kb != null && last.mem_total_kb > 0 && last.mem_available_kb != null
      ? Math.round(((last.mem_total_kb - last.mem_available_kb) / last.mem_total_kb) * 100)
      : null;
  const diskUsedPct =
    last && last.disk_total_kb != null && last.disk_total_kb > 0 && last.disk_used_kb != null
      ? Math.round((last.disk_used_kb / last.disk_total_kb) * 100)
      : null;

  const chartData = metrics.map((m) => ({
    time: formatTime(m.created_at),
    full: m.created_at,
    load: m.load_1 ?? 0,
    mem:
      m.mem_total_kb != null && m.mem_total_kb > 0 && m.mem_available_kb != null
        ? Math.round(((m.mem_total_kb - m.mem_available_kb) / m.mem_total_kb) * 100)
        : 0,
    disk:
      m.disk_total_kb != null && m.disk_total_kb > 0 && m.disk_used_kb != null
        ? Math.round((m.disk_used_kb / m.disk_total_kb) * 100)
        : 0,
  }));

  return (
    <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <ServerIcon className="text-slate-400" size={20} />
          <span className="font-medium text-white">{server.name}</span>
          <span className="text-slate-500 text-sm">{server.host}</span>
        </div>
        <div className="flex items-center gap-4 text-sm flex-wrap">
          <button
            type="button"
            onClick={() => collectNowMut.mutate()}
            disabled={collectNowMut.isPending}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs font-medium disabled:opacity-50"
            title="Собрать метрики сейчас (реальное время)"
          >
            <RefreshCw size={14} className={collectNowMut.isPending ? "animate-spin" : ""} />
            {collectNowMut.isPending ? "Сбор…" : "Обновить сейчас"}
          </button>
          {last?.load_1 != null && (
            <span className="flex items-center gap-1.5 text-slate-300">
              <Cpu size={16} className="text-amber-400" />
              Load: {last.load_1.toFixed(2)}
            </span>
          )}
          {memUsedPct != null && (
            <span className="flex items-center gap-1.5 text-slate-300">
              <MemoryStick size={16} className="text-blue-400" />
              RAM: {memUsedPct}%
            </span>
          )}
          {diskUsedPct != null && (
            <span className="flex items-center gap-1.5 text-slate-300">
              <HardDrive size={16} className="text-emerald-400" />
              Диск: {diskUsedPct}%
            </span>
          )}
        </div>
      </div>
      <div className="p-4">
        {isLoading && <p className="text-slate-500 text-sm">Загрузка метрик...</p>}
        {error && <p className="text-red-400 text-sm">Ошибка загрузки метрик</p>}
        {!isLoading && !error && chartData.length === 0 && (
          <p className="text-slate-500 text-sm">Нет данных за выбранный период. Метрики собираются каждые 5 мин.</p>
        )}
        {chartData.length > 0 && (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} />
                <YAxis yAxisId="load" stroke="#94a3b8" fontSize={11} orientation="left" />
                <YAxis yAxisId="pct" stroke="#94a3b8" fontSize={11} orientation="right" tickFormatter={(v) => `${v}%`} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #475569" }}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.full ?? ""}
                  formatter={(value: number, name: string) => [
                    name === "load" ? value.toFixed(2) : `${value}%`,
                    name === "load" ? "Load (1m)" : name === "mem" ? "RAM" : "Диск",
                  ]}
                />
                <Line yAxisId="load" type="monotone" dataKey="load" stroke="#f59e0b" strokeWidth={1.5} dot={false} name="load" />
                <Line yAxisId="pct" type="monotone" dataKey="mem" stroke="#60a5fa" strokeWidth={1.5} dot={false} name="mem" />
                <Line yAxisId="pct" type="monotone" dataKey="disk" stroke="#34d399" strokeWidth={1.5} dot={false} name="disk" />
              </LineChart>
            </ResponsiveContainer>
            <p className="text-xs text-slate-500 mt-1">— Load (1m) — RAM (%) — Диск (%)</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default function Monitoring() {
  const [period, setPeriod] = useState<"1h" | "24h" | "7d">("24h");
  const { data: servers, isLoading } = useQuery({
    queryKey: ["servers"],
    queryFn: () => api.get<Server[]>("/servers/").then((r) => r.data),
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <h1 className="text-2xl font-bold text-white">Мониторинг VPS</h1>
        <div className="flex items-center gap-2">
          <span className="text-slate-400 text-sm">Период:</span>
          {(["1h", "24h", "7d"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                period === p
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-700 text-slate-300 hover:bg-slate-600"
              }`}
            >
              {p === "1h" ? "1 час" : p === "24h" ? "24 часа" : "7 дней"}
            </button>
          ))}
        </div>
      </div>
      <p className="text-slate-400 text-sm mb-6">
        Нагрузка, RAM и диск по каждому серверу. Данные обновляются каждые 5 мин по расписанию; кнопка «Обновить сейчас» — снимок в реальном времени. Страница подгружает данные каждые 2 мин.
      </p>
      {isLoading ? (
        <p className="text-slate-400">Загрузка списка серверов...</p>
      ) : !servers?.length ? (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 p-8 text-center">
          <ServerIcon className="text-slate-500 mx-auto mb-4" size={48} />
          <p className="text-slate-400">Нет серверов</p>
          <p className="text-slate-500 text-sm mt-1">Добавьте сервер в разделе «Серверы», чтобы видеть метрики</p>
        </div>
      ) : (
        <div className="space-y-6">
          {servers.map((server) => (
            <ServerMonitorCard key={server.id} server={server} period={period} />
          ))}
        </div>
      )}
    </div>
  );
}
