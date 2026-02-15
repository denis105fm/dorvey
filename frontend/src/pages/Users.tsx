import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Users as UsersIcon, UserPlus, Key } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";

type UserRow = {
  id: number;
  email: string;
  role: string;
  created_at: string | null;
  has_2fa: boolean;
};

export default function Users() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ email: "", password: "", role: "user" });
  const [genResult, setGenResult] = useState<{ email: string; password: string } | null>(null);

  const { data: users, error, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserRow[]>("/users/").then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (d: typeof createForm) => api.post("/users/", d).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setShowCreate(false);
      setCreateForm({ email: "", password: "", role: "user" });
    },
  });

  const genMut = useMutation({
    mutationFn: () => api.post("/users/generate").then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["users"] });
      setGenResult({ email: data.email, password: data.password });
    },
  });

  if (error) {
    return (
      <div>
        <h1 className="text-2xl font-bold text-white mb-6">Пользователи</h1>
        <p className="text-red-400">Доступ только для администратора.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <UsersIcon size={28} />
          Пользователи
        </h1>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowCreate(!showCreate); setGenResult(null); }}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium"
          >
            <UserPlus size={18} />
            Создать вручную
          </button>
          <button
            onClick={() => genMut.mutate()}
            disabled={genMut.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm font-medium disabled:opacity-50"
          >
            <Key size={18} />
            {genMut.isPending ? "Генерация..." : "Сгенерировать"}
          </button>
        </div>
      </div>

      {genResult && (
        <div className="mb-6 p-4 bg-amber-900/30 border border-amber-600/50 rounded-xl">
          <p className="text-amber-200 font-medium mb-2">Сохраните данные — пароль больше не покажется:</p>
          <p className="text-white font-mono text-sm">Email: {genResult.email}</p>
          <p className="text-white font-mono text-sm">Пароль: {genResult.password}</p>
          <button onClick={() => setGenResult(null)} className="mt-2 text-slate-400 hover:text-white text-sm">Закрыть</button>
        </div>
      )}

      {showCreate && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Создать пользователя</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={(e) => { e.preventDefault(); createMut.mutate(createForm); }}
              className="grid grid-cols-1 md:grid-cols-4 gap-4"
            >
              <div>
                <label className="block text-slate-400 text-sm mb-1">Email</label>
                <input
                  type="email"
                  value={createForm.email}
                  onChange={(e) => setCreateForm((f) => ({ ...f, email: e.target.value }))}
                  required
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Пароль</label>
                <input
                  type="text"
                  value={createForm.password}
                  onChange={(e) => setCreateForm((f) => ({ ...f, password: e.target.value }))}
                  required
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Роль</label>
                <select
                  value={createForm.role}
                  onChange={(e) => setCreateForm((f) => ({ ...f, role: e.target.value }))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                >
                  <option value="user">user</option>
                  <option value="admin">admin</option>
                  <option value="viewer">viewer</option>
                </select>
              </div>
              <div className="flex items-end gap-2">
                <button
                  type="submit"
                  disabled={createMut.isPending}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm disabled:opacity-50"
                >
                  {createMut.isPending ? "Создание..." : "Создать"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-slate-400 hover:text-white text-sm"
                >
                  Отмена
                </button>
              </div>
            </form>
            {createMut.isError && (
              <p className="mt-2 text-red-400 text-sm">
                {(createMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Ошибка"}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Список пользователей</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-2 text-slate-400">ID</th>
                    <th className="text-left py-2 text-slate-400">Email</th>
                    <th className="text-left py-2 text-slate-400">Роль</th>
                    <th className="text-left py-2 text-slate-400">2FA</th>
                    <th className="text-left py-2 text-slate-400">Создан</th>
                  </tr>
                </thead>
                <tbody>
                  {users?.map((u) => (
                    <tr key={u.id} className="border-b border-slate-700/50">
                      <td className="py-2">{u.id}</td>
                      <td className="py-2 text-white">{u.email}</td>
                      <td className="py-2">
                        <span className={u.role === "admin" ? "text-emerald-400" : "text-slate-300"}>{u.role}</span>
                      </td>
                      <td className="py-2">{u.has_2fa ? "✓" : "—"}</td>
                      <td className="py-2 text-slate-500">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
