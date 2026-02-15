import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

type Server = { id: number; name: string; host: string; port: number; user: string; auth_type?: string; path?: string; ssl_auto?: boolean };

export default function Servers() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [edit, setEdit] = useState<Server | null>(null);
  const [form, setForm] = useState({ name: "", host: "", port: 22, user: "", auth_type: "ssh_key", auth_data: "", path: "/var/www/html", ssl_auto: true });
  const { data: servers, isLoading } = useQuery({
    queryKey: ["servers"],
    queryFn: () => api.get("/servers/").then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (d: typeof form) => api.post("/servers/", d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["servers"] }); setModal(null); setForm({ name: "", host: "", port: 22, user: "", auth_type: "ssh_key", auth_data: "", path: "/var/www/html", ssl_auto: true }); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<typeof form> }) => api.patch(`/servers/${id}`, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["servers"] }); setModal(null); setEdit(null); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/servers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["servers"] }),
  });

  const openEdit = (s: Server) => {
    setEdit(s);
    setForm({ name: s.name, host: s.host, port: s.port, user: s.user, auth_type: s.auth_type || "ssh_key", auth_data: "", path: s.path || "/var/www/html", ssl_auto: s.ssl_auto ?? true });
    setModal("edit");
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Серверы</h1>
        <button onClick={() => { setModal("create"); setForm({ name: "", host: "", port: 22, user: "", auth_type: "ssh_key", auth_data: "", path: "/var/www/html", ssl_auto: true }); }} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">Добавить сервер</button>
      </div>
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {servers?.length ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Название</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Хост</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Порт</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Пользователь</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {servers.map((s: { id: number; name: string; host: string; port: number; user: string }) => (
                  <tr key={s.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-white">{s.id}</td>
                    <td className="px-4 py-3 text-white">{s.name}</td>
                    <td className="px-4 py-3 text-slate-400">{s.host}</td>
                    <td className="px-4 py-3 text-slate-400">{s.port}</td>
                    <td className="px-4 py-3 text-slate-400">{s.user}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => openEdit(s)} className="text-emerald-400 hover:underline text-sm mr-2">Изменить</button>
                      <button onClick={() => deleteMut.mutate(s.id)} className="text-red-400 hover:underline text-sm">Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-slate-400">Пока нет серверов</div>
          )}
        </div>
      )}

      {modal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => { setModal(null); setEdit(null); }}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4">{modal === "create" ? "Новый сервер" : "Редактировать сервер"}</h2>
            <div className="space-y-3">
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Название" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input value={form.host} onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))} placeholder="Хост" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <div className="grid grid-cols-2 gap-3">
                <input type="number" value={form.port} onChange={(e) => setForm((f) => ({ ...f, port: parseInt(e.target.value) || 22 }))} placeholder="Порт" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.user} onChange={(e) => setForm((f) => ({ ...f, user: e.target.value }))} placeholder="Пользователь" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              </div>
              <input value={form.path} onChange={(e) => setForm((f) => ({ ...f, path: e.target.value }))} placeholder="Путь" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <select value={form.auth_type} onChange={(e) => setForm((f) => ({ ...f, auth_type: e.target.value }))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                <option value="ssh_key">SSH ключ</option>
                <option value="password">Пароль</option>
              </select>
              <input value={form.auth_data} onChange={(e) => setForm((f) => ({ ...f, auth_data: e.target.value }))} placeholder={form.auth_type === "password" ? "Пароль" : "Ключ (опц.)"} type={form.auth_type === "password" ? "password" : "text"} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <label className="flex items-center gap-2 text-slate-300"><input type="checkbox" checked={form.ssl_auto} onChange={(e) => setForm((f) => ({ ...f, ssl_auto: e.target.checked }))} />Авто SSL</label>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => { setModal(null); setEdit(null); }} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button onClick={() => modal === "create" ? createMut.mutate(form) : edit && updateMut.mutate({ id: edit.id, data: form })} disabled={!form.name || !form.host || !form.user || createMut.isPending || updateMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white">Сохранить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
