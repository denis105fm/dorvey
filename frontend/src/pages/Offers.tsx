import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

type Offer = { id: number; url: string; geo: string | null; device: string | null; priority: number; is_active: boolean };

export default function Offers() {
  const qc = useQueryClient();
  const [campaignId, setCampaignId] = useState(1);
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [edit, setEdit] = useState<Offer | null>(null);
  const [form, setForm] = useState({ url: "", geo: "", device: "", priority: 0, is_active: true });

  const { data: offers, isLoading } = useQuery({
    queryKey: ["offers", campaignId],
    queryFn: () => api.get("/offers/", { params: { campaign_id: campaignId } }).then((r) => r.data),
    enabled: !!campaignId,
  });
  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (d: typeof form & { campaign_id: number }) => api.post("/offers/", { ...d, campaign_id: campaignId, geo: d.geo || undefined, device: d.device || undefined }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["offers", campaignId] }); setModal(null); setForm({ url: "", geo: "", device: "", priority: 0, is_active: true }); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<typeof form> }) => api.patch(`/offers/${id}`, { ...data, geo: data.geo || undefined, device: data.device || undefined }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["offers", campaignId] }); setModal(null); setEdit(null); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/offers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["offers", campaignId] }),
  });

  const openEdit = (o: Offer) => {
    setEdit(o);
    setForm({ url: o.url, geo: o.geo ?? "", device: o.device ?? "", priority: o.priority, is_active: o.is_active });
    setModal("edit");
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Офферы</h1>
      <div className="mb-4 flex items-center gap-4">
        <div>
          <label className="block text-slate-400 text-sm mb-2">Кампания</label>
          <select value={campaignId} onChange={(e) => setCampaignId(Number(e.target.value))} className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-64">
            {campaigns?.map((c: { id: number; name: string }) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <button onClick={() => { setModal("create"); setForm({ url: "", geo: "", device: "", priority: 0, is_active: true }); }} className="mt-6 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">Добавить оффер</button>
      </div>
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {offers?.length ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">URL</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Geo</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Device</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Приоритет</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Активен</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {offers.map((o: Offer) => (
                  <tr key={o.id} className="border-b border-slate-700/50">
                    <td className="px-4 py-3 text-white">{o.id}</td>
                    <td className="px-4 py-3 text-slate-400 truncate max-w-xs">{o.url}</td>
                    <td className="px-4 py-3 text-slate-400">{o.geo ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{o.device ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{o.priority}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${o.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-600 text-slate-400"}`}>{o.is_active ? "Да" : "Нет"}</span>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => openEdit(o)} className="text-emerald-400 hover:underline text-sm mr-2">Изменить</button>
                      <button onClick={() => window.confirm("Удалить?") && deleteMut.mutate(o.id)} disabled={deleteMut.isPending} className="text-red-400 hover:underline text-sm">Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-slate-400">Нет офферов для этой кампании</div>
          )}
        </div>
      )}

      {modal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => { setModal(null); setEdit(null); }}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4">{modal === "create" ? "Новый оффер" : "Редактировать оффер"}</h2>
            <div className="space-y-3">
              <input value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} placeholder="https://..." className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input value={form.geo} onChange={(e) => setForm((f) => ({ ...f, geo: e.target.value }))} placeholder="Geo (RU, US...)" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input value={form.device} onChange={(e) => setForm((f) => ({ ...f, device: e.target.value }))} placeholder="Device (mobile, desktop...)" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input type="number" value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value) || 0 }))} placeholder="Приоритет" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <label className="flex items-center gap-2 text-slate-300">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
                Активен
              </label>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => { setModal(null); setEdit(null); }} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button onClick={() => modal === "create" ? createMut.mutate({ ...form, campaign_id: campaignId }) : edit && updateMut.mutate({ id: edit.id, data: form })} disabled={!form.url || createMut.isPending || updateMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white">Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
