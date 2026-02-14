import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

export default function Keywords() {
  const qc = useQueryClient();
  const [campaignId, setCampaignId] = useState(1);
  const [volume, setVolume] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: keywords, isLoading } = useQuery({
    queryKey: ["keywords", campaignId],
    queryFn: () => api.get("/keywords/", { params: { campaign_id: campaignId } }).then((r) => r.data),
    enabled: !!campaignId,
  });

  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });

  const bulkMut = useMutation({
    mutationFn: (data: { campaign_id: number; keywords: string[]; volume: number }) => api.post("/keywords/bulk", data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["keywords", campaignId] }); fileRef.current && (fileRef.current.value = ""); },
  });

  const handleCsvImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !campaignId) return;
    const r = new FileReader();
    r.onload = () => {
      const text = (r.result as string) || "";
      const lines = text.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
      const kw = lines.flatMap((line) => {
        const parts = line.split(/[,;\t]/).map((p) => p.trim()).filter(Boolean);
        return parts.length ? parts : [line];
      });
      if (kw.length) bulkMut.mutate({ campaign_id: campaignId, keywords: kw, volume: volume });
    };
    r.readAsText(file, "utf-8");
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Ключевые слова</h1>
      <div className="mb-4 flex flex-wrap items-end gap-4">
        <div>
          <label className="block text-slate-400 text-sm mb-2">Кампания</label>
          <select
            value={campaignId}
            onChange={(e) => setCampaignId(+e.target.value)}
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-64"
          >
            {campaigns?.map((c: { id: number; name: string }) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input type="file" ref={fileRef} accept=".csv,.txt" onChange={handleCsvImport} className="hidden" />
          <input type="number" value={volume} onChange={(e) => setVolume(parseInt(e.target.value) || 0)} placeholder="Объём" className="w-24 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
          <button onClick={() => fileRef.current?.click()} disabled={bulkMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm">Импорт CSV</button>
        </div>
      </div>
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {keywords?.length ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Ключевое слово</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Кластер</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Объём</th>
                </tr>
              </thead>
              <tbody>
                {keywords.map((k: { id: number; keyword: string; cluster_id: number | null; volume: number }) => (
                  <tr key={k.id} className="border-b border-slate-700/50">
                    <td className="px-4 py-3 text-white">{k.id}</td>
                    <td className="px-4 py-3 text-white">{k.keyword}</td>
                    <td className="px-4 py-3 text-slate-400">{k.cluster_id ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{k.volume}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-slate-400">Нет ключевых слов для этой кампании</div>
          )}
        </div>
      )}
    </div>
  );
}
