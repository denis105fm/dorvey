import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

export default function Templates() {
  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get("/templates/").then((r) => r.data),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Шаблоны</h1>
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {templates?.length ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Название</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Тип</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((t: { id: number; name: string; type: string }) => (
                  <tr key={t.id} className="border-b border-slate-700/50">
                    <td className="px-4 py-3 text-white">{t.id}</td>
                    <td className="px-4 py-3 text-white">{t.name}</td>
                    <td className="px-4 py-3 text-slate-400">{t.type}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-slate-400">Пока нет шаблонов</div>
          )}
        </div>
      )}
    </div>
  );
}
