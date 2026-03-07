import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Globe } from "lucide-react";

type Domain = { id: number; domain: string; server_id: number; campaign_id: number | null; status: string };

export default function Domains() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [edit, setEdit] = useState<Domain | null>(null);
  const [form, setForm] = useState({ domain: "", server_id: 1, campaign_id: "" as string | number, status: "pending" });

  const { data: domains, isLoading } = useQuery({
    queryKey: ["domains"],
    queryFn: () => api.get("/domains/").then((r) => r.data),
  });
  const { data: servers } = useQuery({ queryKey: ["servers"], queryFn: () => api.get("/servers/").then((r) => r.data) });
  const { data: campaigns } = useQuery({ queryKey: ["campaigns"], queryFn: () => api.get("/campaigns/").then((r) => r.data) });

  const createMut = useMutation({
    mutationFn: (d: { domain: string; server_id: number; campaign_id?: number; status: string }) => api.post("/domains/", { ...d, campaign_id: d.campaign_id || undefined }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["domains"] }); setModal(null); resetForm(); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { server_id?: number; campaign_id?: number | null; status?: string } }) => api.patch(`/domains/${id}`, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["domains"] }); setModal(null); setEdit(null); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/domains/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["domains"] }),
  });

  function resetForm() {
    setForm({ domain: "", server_id: servers?.[0]?.id ?? 1, campaign_id: "", status: "pending" });
  }

  const openEdit = (d: Domain) => {
    setEdit(d);
    setForm({ domain: d.domain, server_id: d.server_id, campaign_id: d.campaign_id ?? "", status: d.status });
    setModal("edit");
  };

  const createPayload = () => ({
    domain: form.domain,
    server_id: form.server_id,
    campaign_id: form.campaign_id ? Number(form.campaign_id) : undefined,
    status: form.status,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Домены</h1>
        <button onClick={() => { setModal("create"); setForm({ domain: "", server_id: servers?.[0]?.id ?? 1, campaign_id: "", status: "pending" }); }} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">Добавить домен</button>
      </div>
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {domains?.length ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Домен</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Сервер</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Кампания</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Статус</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {domains.map((d: Domain) => (
                  <tr key={d.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-white">{d.id}</td>
                    <td className="px-4 py-3 text-white">{d.domain}</td>
                    <td className="px-4 py-3 text-slate-400">{d.server_id}</td>
                    <td className="px-4 py-3 text-slate-400">{d.campaign_id ?? "—"}</td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 rounded text-xs bg-slate-600 text-slate-300">{d.status}</span></td>
                    <td className="px-4 py-3">
                      <button onClick={() => openEdit(d)} className="text-emerald-400 hover:underline text-sm mr-2">Изменить</button>
                      <button onClick={() => window.confirm("Удалить?") && deleteMut.mutate(d.id)} disabled={deleteMut.isPending} className="text-red-400 hover:underline text-sm">Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center">
              <div className="rounded-full bg-slate-700/50 w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <Globe className="text-slate-500" size={32} strokeWidth={1.5} />
              </div>
              <p className="text-slate-400">Пока нет доменов</p>
              <p className="text-slate-500 text-sm mt-1">Добавьте домен для деплоя дорвеев</p>
              <button onClick={() => setModal("create")} className="mt-4 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm">
                Добавить домен
              </button>
            </div>
          )}
        </div>
      )}

      {modal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => { setModal(null); setEdit(null); }}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4">{modal === "create" ? "Новый домен" : "Редактировать домен"}</h2>
            <div className="space-y-3">
              {modal === "create" && (
                <input value={form.domain} onChange={(e) => setForm((f) => ({ ...f, domain: e.target.value }))} placeholder="example.com" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              )}
              <div>
                <label className="block text-slate-400 text-sm mb-1">Сервер</label>
                <select value={form.server_id} onChange={(e) => setForm((f) => ({ ...f, server_id: Number(e.target.value) }))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                  {servers?.map((s: { id: number; name: string }) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Кампания</label>
                <select value={form.campaign_id} onChange={(e) => setForm((f) => ({ ...f, campaign_id: e.target.value }))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                  <option value="">— не выбрана</option>
                  {campaigns?.map((c: { id: number; name: string; is_black?: boolean }) => (
                    <option key={c.id} value={c.id}>{c.name}{c.is_black ? " (чёрные)" : ""}</option>
                  ))}
                </select>
                {modal === "create" && (() => {
                  const camp = campaigns?.find((c: { id: number; is_black?: boolean }) => c.id === Number(form.campaign_id));
                  return camp?.is_black ? <p className="text-amber-400 text-xs mt-1">Чёрная кампания — выберите отдельный сервер для чёрных дорвеев.</p> : null;
                })()}
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Статус</label>
                <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                  <option value="pending">pending</option>
                  <option value="active">active</option>
                  <option value="inactive">inactive</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => { setModal(null); setEdit(null); }} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button
                onClick={() => modal === "create"
                  ? createMut.mutate(createPayload())
                  : edit && updateMut.mutate({ id: edit.id, data: { server_id: form.server_id, campaign_id: form.campaign_id ? Number(form.campaign_id) : null, status: form.status } })}
                disabled={(modal === "create" && !form.domain) || createMut.isPending || updateMut.isPending}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white"
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
