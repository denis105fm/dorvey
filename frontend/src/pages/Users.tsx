import { useQuery } from "@tanstack/react-query";
import api from "../api/client";
import { Users as UsersIcon } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/card";

type UserRow = {
  id: number;
  email: string;
  role: string;
  created_at: string | null;
  has_2fa: boolean;
};

export default function Users() {
  const { data: users, error, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserRow[]>("/users/").then((r) => r.data),
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
      <h1 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
        <UsersIcon size={28} />
        Пользователи
      </h1>
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
