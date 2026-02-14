import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

type Campaign = {
  id: number;
  name: string;
  affiliate_url?: string | null;
  language: string;
  locale: string;
  region: string;
  currency: string;
  status: string;
};

export default function Campaigns() {
  const qc = useQueryClient();
  const [abCampaignId, setAbCampaignId] = useState<number | null>(null);
  const [rulesCampaignId, setRulesCampaignId] = useState<number | null>(null);
  const [trafficCampaignId, setTrafficCampaignId] = useState<number | null>(null);
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [edit, setEdit] = useState<Campaign | null>(null);
  const [form, setForm] = useState({ name: "", affiliate_url: "", language: "ru", locale: "ru-RU", region: "RU", currency: "RUB", status: "active" });

  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: abWinner, isLoading: abLoading } = useQuery({
    queryKey: ["ab-winner", abCampaignId],
    queryFn: () => api.get(`/optimizer/campaign/${abCampaignId}/ab-winner?days=14`).then((r) => r.data),
    enabled: !!abCampaignId,
  });
  const { data: trafficMix } = useQuery({
    queryKey: ["traffic-mix", trafficCampaignId],
    queryFn: () => api.get(`/optimizer/campaign/${trafficCampaignId}/traffic-mix?days=14`).then((r) => r.data),
    enabled: !!trafficCampaignId,
  });
  const { data: rules, isLoading: rulesLoading } = useQuery({
    queryKey: ["rules", rulesCampaignId],
    queryFn: () => api.get(`/rules/campaign/${rulesCampaignId}`).then((r) => r.data),
    enabled: !!rulesCampaignId,
  });

  const createMut = useMutation({
    mutationFn: (d: typeof form) => api.post("/campaigns/", d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campaigns"] }); setModal(null); setForm({ name: "", affiliate_url: "", language: "ru", locale: "ru-RU", region: "RU", currency: "RUB", status: "active" }); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<typeof form> }) => api.patch(`/campaigns/${id}`, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campaigns"] }); setModal(null); setEdit(null); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/campaigns/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
  const updateRulesMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.put(`/rules/campaign/${rulesCampaignId}`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rules", rulesCampaignId] }),
  });

  const openEdit = (c: Campaign) => {
    setEdit(c);
    setForm({ name: c.name, affiliate_url: c.affiliate_url ?? "", language: c.language, locale: c.locale, region: c.region, currency: c.currency, status: c.status });
    setModal("edit");
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Кампании</h1>
        <button onClick={() => { setModal("create"); setForm({ name: "", affiliate_url: "", language: "ru", locale: "ru-RU", region: "RU", currency: "RUB", status: "active" }); }}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">
          Добавить кампанию
        </button>
      </div>
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="space-y-6">
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
            {campaigns?.length ? (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Название</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Язык</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Регион</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Статус</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c: Campaign) => (
                    <tr key={c.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-white">{c.id}</td>
                      <td className="px-4 py-3 text-white">{c.name}</td>
                      <td className="px-4 py-3 text-slate-400">{c.language}</td>
                      <td className="px-4 py-3 text-slate-400">{c.region}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400">{c.status}</span>
                      </td>
                      <td className="px-4 py-3 flex gap-2 flex-wrap">
                        <button onClick={() => setAbCampaignId(abCampaignId === c.id ? null : c.id)} className="text-amber-400 hover:underline text-sm">A/B</button>
                        <button onClick={() => setTrafficCampaignId(trafficCampaignId === c.id ? null : c.id)} className="text-blue-400 hover:underline text-sm">Traffic mix</button>
                        <button onClick={() => setRulesCampaignId(rulesCampaignId === c.id ? null : c.id)} className="text-violet-400 hover:underline text-sm">Правила</button>
                        <button onClick={() => openEdit(c)} className="text-emerald-400 hover:underline text-sm">Изменить</button>
                        <button onClick={() => window.confirm("Удалить?") && deleteMut.mutate(c.id)} disabled={deleteMut.isPending} className="text-red-400 hover:underline text-sm">Удалить</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-8 text-center text-slate-400">Пока нет кампаний</div>
            )}
          </div>
          {abCampaignId && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">A/B Winner — кампания #{abCampaignId}
                <button onClick={() => setAbCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              {abLoading ? <p className="text-slate-400">Загрузка...</p> : abWinner && (
                <div className="space-y-2 text-slate-300 text-sm">
                  <p>{abWinner.message}</p>
                  {abWinner.winner !== null && (
                    <p className="text-emerald-400">Лучший layout: {abWinner.winner} (CR: {abWinner.winner_cr}%, revenue: {abWinner.winner_revenue?.toFixed(2)})</p>
                  )}
                  {abWinner.variants?.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {abWinner.variants.map((v: { layout_index: number; cr_percent: number; revenue: number; clicks: number; doorways_count: number }) => (
                        <li key={v.layout_index}>Layout {v.layout_index}: CR={v.cr_percent}%, revenue={v.revenue?.toFixed(2)}, клики={v.clicks}, дорвеев={v.doorways_count}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
          {trafficCampaignId && trafficMix && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">Traffic mix — кампания #{trafficCampaignId}
                <button onClick={() => setTrafficCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              <pre className="text-slate-300 text-sm overflow-auto">{JSON.stringify(trafficMix, null, 2)}</pre>
            </div>
          )}
          {rulesCampaignId && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">Правила кампании #{rulesCampaignId}
                <button onClick={() => setRulesCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              {rulesLoading ? <p className="text-slate-400">Загрузка...</p> : rules && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Запрещённые слова (через запятую)</label>
                    <input value={(rules.forbidden_words || []).join(", ")} onChange={(e) => updateRulesMut.mutate({ forbidden_words: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Разрешённые GEO (через запятую)</label>
                    <input value={(rules.allowed_geo || []).join(", ")} onChange={(e) => updateRulesMut.mutate({ allowed_geo: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 text-slate-300">
                      <input type="checkbox" checked={rules.require_disclaimer ?? false} onChange={(e) => updateRulesMut.mutate({ require_disclaimer: e.target.checked })} />
                      Disclaimer обязателен
                    </label>
                    <label className="flex items-center gap-2 text-slate-300">
                      <input type="checkbox" checked={rules.auto_switch_on_cr_drop ?? false} onChange={(e) => updateRulesMut.mutate({ auto_switch_on_cr_drop: e.target.checked })} />
                      Автосмена оффера при падении CR
                    </label>
                    <label className="flex items-center gap-2 text-slate-300">
                      <input type="checkbox" checked={rules.auto_rollback_on_cr_drop ?? false} onChange={(e) => updateRulesMut.mutate({ auto_rollback_on_cr_drop: e.target.checked })} />
                      Автооткат при падении CR
                    </label>
                  </div>
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Порог отката (% падения CR)</label>
                    <input type="number" value={rules.rollback_threshold_percent ?? 15} onChange={(e) => updateRulesMut.mutate({ rollback_threshold_percent: parseFloat(e.target.value) || 15 })}
                      className="w-32 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {modal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => { setModal(null); setEdit(null); }}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4">{modal === "create" ? "Новая кампания" : "Редактировать кампанию"}</h2>
            <div className="space-y-3">
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Название" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input value={form.affiliate_url} onChange={(e) => setForm((f) => ({ ...f, affiliate_url: e.target.value }))} placeholder="Affiliate URL" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <div className="grid grid-cols-2 gap-3">
                <input value={form.language} onChange={(e) => setForm((f) => ({ ...f, language: e.target.value }))} placeholder="Язык" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.region} onChange={(e) => setForm((f) => ({ ...f, region: e.target.value }))} placeholder="Регион" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.locale} onChange={(e) => setForm((f) => ({ ...f, locale: e.target.value }))} placeholder="Locale" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))} placeholder="Валюта" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              </div>
              <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                <option value="active">active</option>
                <option value="paused">paused</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => { setModal(null); setEdit(null); }} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button onClick={() => modal === "create" ? createMut.mutate(form) : edit && updateMut.mutate({ id: edit.id, data: form })} disabled={!form.name || createMut.isPending || updateMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white">Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
