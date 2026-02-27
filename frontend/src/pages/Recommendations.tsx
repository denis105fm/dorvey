import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

type Rec = {
  country: string;
  offer_count: number;
  our_clicks: number;
  external_news_count: number;
  external_seasonality: boolean;
  sources_used: string[];
  priority_score: number;
  recommended: boolean;
};

export default function Recommendations() {
  const [days, setDays] = useState(30);
  const { data, isLoading } = useQuery({
    queryKey: ["offer-country-recommendations", days],
    queryFn: () =>
      api.get("/analytics/offer-country-recommendations", { params: { days } }).then((r) => r.data as { recommendations: Rec[]; period_days: number }),
  });

  const list = data?.recommendations ?? [];

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Рекомендации по офферам и странам</h1>
      <p className="text-slate-400 text-sm mb-4 max-w-2xl">
        По гео из ваших офферов: наши клики за период и внешние данные (новости, сезонность). Рекомендуемые — страны с офферами и трафиком или внешними сигналами.
      </p>
      <div className="mb-4 flex items-center gap-4">
        <label className="text-slate-400 text-sm">Период (дней)</label>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
        >
          <option value={7}>7</option>
          <option value={14}>14</option>
          <option value={30}>30</option>
          <option value={90}>90</option>
        </select>
      </div>

      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : !list.length ? (
        <div className="p-8 rounded-xl bg-slate-800/80 border border-slate-600 text-center text-slate-400">
          Нет гео в офферах. Добавьте офферы с указанием страны в разделе Офферы.
        </div>
      ) : (
        <div className="card-volumetric overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Страна</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Офферов</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Наши клики</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Новости</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Источники</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Сезонность</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Приоритет</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Рекомендуем</th>
                </tr>
              </thead>
              <tbody>
                {list.map((r: Rec) => (
                  <tr key={r.country} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3">
                      <span className="font-medium text-white uppercase">{r.country}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{r.offer_count}</td>
                    <td className="px-4 py-3 text-slate-300">{r.our_clicks}</td>
                    <td className="px-4 py-3 text-slate-400">{r.external_news_count > 0 ? r.external_news_count : "—"}</td>
                    <td className="px-4 py-3">
                      {(r.sources_used?.length ?? 0) > 0 ? (
                        <span className="text-xs text-slate-400" title={r.sources_used?.join(", ")}>
                          {r.sources_used?.slice(0, 3).join(", ")}
                          {(r.sources_used?.length ?? 0) > 3 ? "…" : ""}
                        </span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {r.external_seasonality ? (
                        <span className="text-emerald-400 text-sm">Да</span>
                      ) : (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-300">{r.priority_score}</td>
                    <td className="px-4 py-3">
                      {r.recommended ? (
                        <span className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400">Да</span>
                      ) : (
                        <span className="text-slate-500 text-sm">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {list.length > 0 && (
        <p className="text-slate-500 text-xs mt-4">
          Включите «Внешние данные» в Настройках и укажите хотя бы один источник. Регистрация: <a href="https://newsapi.org/register" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">NewsAPI</a>, <a href="https://gnews.io/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">GNews</a>, <a href="https://mediastack.com/signup" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Mediastack</a>, <a href="https://open-platform.theguardian.com/access/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Guardian</a>. REST Countries подключается автоматически.
        </p>
      )}
    </div>
  );
}
