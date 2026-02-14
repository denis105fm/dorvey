import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

export default function Analytics() {
  const [days, setDays] = useState(30);

  const { data: summary } = useQuery({
    queryKey: ["analytics-summary", days],
    queryFn: () => api.get("/analytics/summary", { params: { days } }).then((r) => r.data),
  });

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
