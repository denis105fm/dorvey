import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";

type Rec = { type: string; text: string };

export default function Doorways() {
  const qc = useQueryClient();
  const [showGenerate, setShowGenerate] = useState(false);
  const [gen, setGen] = useState({ campaign_id: 1, domain_id: 1, keyword: "", path: "/", save: true });
  const [batchKeywords, setBatchKeywords] = useState("");
  const [result, setResult] = useState<{ html?: string; doorway_id?: number; validation_violations?: string[] } | null>(null);
  const [recsDoorwayId, setRecsDoorwayId] = useState<number | null>(null);
  const [panelDoorwayId, setPanelDoorwayId] = useState<number | null>(null);
  const [panelType, setPanelType] = useState<"quality" | "predict" | "broken" | null>(null);

  const { data: doorways, isLoading } = useQuery({
    queryKey: ["doorways"],
    queryFn: () => api.get("/doorways/").then((r) => r.data),
  });
  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: domains } = useQuery({
    queryKey: ["domains"],
    queryFn: () => api.get("/domains/").then((r) => r.data),
  });
  const generateMut = useMutation({
    mutationFn: (d: typeof gen) => api.post("/doorways/generate", d).then((r) => r.data),
    onSuccess: (data) => { setResult(data); qc.invalidateQueries({ queryKey: ["doorways"] }); },
  });
  const deployMut = useMutation({
    mutationFn: (id: number) => api.post(`/deploy/doorway/${id}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["doorways"] }),
  });
  const batchMut = useMutation({
    mutationFn: (items: { campaign_id: number; domain_id: number; keyword: string; path: string }[]) =>
      api.post("/doorways/generate-batch", { items }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["doorways"] }),
  });
  const rollbackMut = useMutation({
    mutationFn: (id: number) => api.post(`/optimizer/doorway/${id}/rollback`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["doorways"] }),
  });
  const { data: recs } = useQuery({
    queryKey: ["recommendations", recsDoorwayId],
    queryFn: () => api.get(`/optimizer/doorway/${recsDoorwayId}/recommendations?days=14`).then((r) => r.data),
    enabled: !!recsDoorwayId,
  });
  const applyRecMut = useMutation({
    mutationFn: ({ id, rec }: { id: number; rec: Rec }) =>
      api.post(`/optimizer/doorway/${id}/apply-recommendation`, { rec_type: rec.type, rec_text: rec.text }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["doorways"] }); qc.invalidateQueries({ queryKey: ["recommendations", recsDoorwayId] }); },
  });

  const { data: qualityCheck } = useQuery({
    queryKey: ["quality-check", panelDoorwayId],
    queryFn: () => api.get(`/doorways/${panelDoorwayId}/quality-check`).then((r) => r.data),
    enabled: !!panelDoorwayId && panelType === "quality",
  });
  const { data: predictCr } = useQuery({
    queryKey: ["predict-cr", panelDoorwayId],
    queryFn: () => api.get(`/optimizer/doorway/${panelDoorwayId}/predict-cr?days=30`).then((r) => r.data),
    enabled: !!panelDoorwayId && panelType === "predict",
  });
  const { data: brokenLinks } = useQuery({
    queryKey: ["broken-links", panelDoorwayId],
    queryFn: () => api.get(`/broken-links/doorway/${panelDoorwayId}`).then((r) => r.data),
    enabled: !!panelDoorwayId && panelType === "broken",
  });
  const repairMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { broken_urls: string[]; replacement?: string } }) =>
      api.post(`/broken-links/doorway/${id}/repair`, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["broken-links", panelDoorwayId] }); qc.invalidateQueries({ queryKey: ["doorways"] }); },
  });

  const openPanel = (id: number, type: "quality" | "predict" | "broken") => {
    setPanelDoorwayId(id);
    setPanelType(type);
  };
  const closePanel = () => { setPanelDoorwayId(null); setPanelType(null); };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Дорвеи</h1>
        <button onClick={() => setShowGenerate(!showGenerate)}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">
          {showGenerate ? "Скрыть" : "Сгенерировать"}
        </button>
      </div>
      {showGenerate && (
        <div className="mb-6 p-5 bg-slate-800/80 rounded-xl border border-slate-700">
          <h2 className="text-lg font-medium text-white mb-4">Генерация дорвея (AI)</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
            <div>
              <label className="block text-slate-400 text-sm mb-1">Кампания</label>
              <select value={gen.campaign_id} onChange={(e) => setGen((g) => ({ ...g, campaign_id: +e.target.value }))}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                {campaigns?.map((c: { id: number; name: string }) => <option key={c.id} value={c.id}>{c.name}</option>)}
                {(!campaigns?.length) && <option value={1}>—</option>}
              </select>
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Домен</label>
              <select value={gen.domain_id} onChange={(e) => setGen((g) => ({ ...g, domain_id: +e.target.value }))}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                {domains?.map((d: { id: number; domain: string }) => <option key={d.id} value={d.id}>{d.domain}</option>)}
                {(!domains?.length) && <option value={1}>—</option>}
              </select>
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Ключевое слово</label>
              <input value={gen.keyword} onChange={(e) => setGen((g) => ({ ...g, keyword: e.target.value }))}
                placeholder="кредит наличными"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500" />
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Путь</label>
              <input value={gen.path} onChange={(e) => setGen((g) => ({ ...g, path: e.target.value || "/" }))}
                placeholder="/"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
            </div>
          </div>
          <div className="mt-4 p-3 bg-slate-900/50 rounded-lg">
            <label className="block text-slate-400 text-sm mb-2">Пакетная генерация (по 1 ключу на строку)</label>
            <textarea value={batchKeywords} onChange={(e) => setBatchKeywords(e.target.value)}
              placeholder="кредит наличными\nзайм онлайн\nмикрозайм"
              rows={3}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm" />
            <button onClick={() => {
              const kws = batchKeywords.split("\n").map((k) => k.trim()).filter(Boolean);
              if (!kws.length) return;
              const slug = (s: string) => s.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9а-яё-]/gi, "");
              const items = kws.map((keyword) => ({
                campaign_id: gen.campaign_id,
                domain_id: gen.domain_id,
                keyword,
                path: gen.path === "/" ? `/${slug(keyword)}` : gen.path,
              }));
              batchMut.mutate(items);
            }} disabled={batchMut.isPending || !batchKeywords.trim()}
              className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm">
              {batchMut.isPending ? "Генерация..." : "Сгенерировать пакет"}
            </button>
            {batchMut.data && (
              <p className="mt-2 text-slate-400 text-sm">
                Создано: {batchMut.data.created} из {batchMut.data.results?.length ?? 0}
              </p>
            )}
          </div>
          <div className="flex items-center gap-4 mt-4">
            <label className="flex items-center gap-2 text-slate-300">
              <input type="checkbox" checked={gen.save} onChange={(e) => setGen((g) => ({ ...g, save: e.target.checked }))} />
              Сохранить в базу
            </label>
            <button onClick={() => generateMut.mutate(gen)} disabled={!gen.keyword.trim() || generateMut.isPending}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm">
              {generateMut.isPending ? "Генерация..." : "Сгенерировать"}
            </button>
          </div>
          {generateMut.error && <p className="mt-2 text-red-400 text-sm">Ошибка</p>}
          {result?.validation_violations?.length ? (
            <p className="mt-2 text-amber-400 text-sm">Нарушения: {result.validation_violations.join(", ")}</p>
          ) : null}
          {result?.html && (
            <div className="mt-4">
              <p className="text-slate-400 text-sm mb-2">
                {result.doorway_id ? "Создан дорвей #" + result.doorway_id : "Превью"}
              </p>
              <iframe srcDoc={result.html} title="Preview" className="w-full h-64 border border-slate-600 rounded-lg bg-white" sandbox="allow-same-origin" />
            </div>
          )}
        </div>
      )}
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {doorways?.length ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Кампания</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Путь</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Статус</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {doorways.map((d: { id: number; campaign_id: number; path: string; status: string }) => (
                  <tr key={d.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-white">{d.id}</td>
                    <td className="px-4 py-3 text-slate-400">{d.campaign_id}</td>
                    <td className="px-4 py-3 text-white">{d.path || "/"}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${d.status === "deployed" ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-600 text-slate-300"}`}>{d.status}</span>
                    </td>
                    <td className="px-4 py-3 flex gap-2 flex-wrap">
                      {d.status !== "deployed" && (
                        <button onClick={() => deployMut.mutate(d.id)} disabled={deployMut.isPending}
                          className="text-emerald-400 hover:underline text-sm">Deploy</button>
                      )}
                      <button onClick={() => setRecsDoorwayId(recsDoorwayId === d.id ? null : d.id)}
                        className="text-blue-400 hover:underline text-sm">Рекомендации</button>
                      <button onClick={() => openPanel(d.id, "quality")} className="text-violet-400 hover:underline text-sm">Quality</button>
                      <button onClick={() => openPanel(d.id, "predict")} className="text-cyan-400 hover:underline text-sm">Predict CR</button>
                      <button onClick={() => openPanel(d.id, "broken")} className="text-orange-400 hover:underline text-sm">Битые ссылки</button>
                      <button onClick={() => rollbackMut.mutate(d.id)} disabled={rollbackMut.isPending}
                        className="text-amber-400 hover:underline text-sm">Rollback</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-slate-400">Пока нет дорвеев</div>
          )}
        </div>
      )}
      {panelDoorwayId && panelType && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={closePanel}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-3">
              {panelType === "quality" && "Quality Check"}
              {panelType === "predict" && "Predict CR"}
              {panelType === "broken" && "Битые ссылки"}
              {" — дорвей #" + panelDoorwayId}
              <button onClick={closePanel} className="ml-2 text-slate-400 hover:text-white">✕</button>
            </h2>
            {panelType === "quality" && (
              qualityCheck ? (
                <div className="space-y-2 text-sm">
                  <p className={qualityCheck.ok ? "text-emerald-400" : "text-amber-400"}>{qualityCheck.ok ? "✓ Прошёл проверку" : "⚠ Есть замечания"}</p>
                  {qualityCheck.errors?.length ? <p className="text-red-400">Ошибки: {qualityCheck.errors.join(", ")}</p> : null}
                  {qualityCheck.warnings?.length ? <p className="text-amber-400">Предупреждения: {qualityCheck.warnings.join(", ")}</p> : null}
                </div>
              ) : <p className="text-slate-400">Загрузка...</p>
            )}
            {panelType === "predict" && (
              predictCr ? (
                <pre className="text-slate-300 text-sm whitespace-pre-wrap">{JSON.stringify(predictCr, null, 2)}</pre>
              ) : <p className="text-slate-400">Загрузка...</p>
            )}
            {panelType === "broken" && (
              brokenLinks ? (
                <div className="space-y-3">
                  {(() => {
                    const broken = Array.isArray(brokenLinks) ? brokenLinks.filter((x: { broken?: boolean }) => x.broken).map((x: { url: string }) => x.url) : [];
                    return broken.length ? (
                      <>
                        <p className="text-slate-400 text-sm">Найдено битых ссылок: {broken.length}</p>
                        <ul className="space-y-1 text-slate-300 text-sm">
                          {broken.map((url: string, i: number) => <li key={i} className="truncate">{url}</li>)}
                        </ul>
                        <div className="flex gap-2 items-center">
                          <input id="replacement" placeholder="Замена (по умолчанию #)" className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm" />
                          <button onClick={() => {
                            const inp = document.getElementById("replacement") as HTMLInputElement;
                            repairMut.mutate({ id: panelDoorwayId!, data: { broken_urls: broken, replacement: inp?.value || "#" } });
                          }} disabled={repairMut.isPending} className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm rounded-lg">
                            Исправить
                          </button>
                        </div>
                      </>
                    ) : <p className="text-emerald-400 text-sm">Битых ссылок не найдено</p>;
                  })()}
                </div>
              ) : <p className="text-slate-400">Загрузка...</p>
            )}
          </div>
        </div>
      )}
      {recsDoorwayId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setRecsDoorwayId(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-5 max-w-lg w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-3">
              Рекомендации — дорвей #{recsDoorwayId}
              <button onClick={() => setRecsDoorwayId(null)} className="ml-2 text-slate-400 hover:text-white">✕</button>
            </h2>
            {recs?.length ? (
              <ul className="space-y-3">
                {recs.map((r: Rec, i: number) => (
                  <li key={i} className="flex items-start justify-between gap-3 p-2 bg-slate-700/50 rounded-lg">
                    <span className="text-slate-300 text-sm">{r.text}</span>
                    <button
                      onClick={() => applyRecMut.mutate({ id: recsDoorwayId!, rec: r })}
                      disabled={applyRecMut.isPending || r.type === "info"}
                      className="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs rounded shrink-0"
                    >
                      {r.type === "info" ? "—" : "Применить"}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-slate-400 text-sm">Загрузка или нет рекомендаций...</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
