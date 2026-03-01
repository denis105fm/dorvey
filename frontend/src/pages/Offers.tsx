import { useRef, useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";

/** Разбивает распознанный текст страницы оффера на Description / Restrictions / Our recommendations */
function parseOfferPageText(fullText: string): { description: string; restrictions: string; recommendations: string } {
  const t = fullText.trim();
  if (!t) return { description: "", restrictions: "", recommendations: "" };
  const lower = t.toLowerCase();
  const restrIdx = lower.indexOf("restrictions");
  let description = t,
    restrictions = "",
    recommendations = "";
  if (restrIdx >= 0) {
    description = t.slice(0, restrIdx).trim();
    const recStart = lower.indexOf("our recommendations", restrIdx);
    if (recStart >= 0) {
      restrictions = t.slice(restrIdx + "restrictions".length, recStart).trim();
      recommendations = t.slice(recStart + "our recommendations".length).trim();
    } else {
      restrictions = t.slice(restrIdx + "restrictions".length).trim();
    }
  }
  return { description, restrictions, recommendations };
}

type Offer = { id: number; url: string; name?: string | null; rate?: string | null; amount?: string | null; term?: string | null; geo: string | null; device: string | null; priority: number; is_active: boolean; description?: string | null; restrictions?: string | null; recommendations?: string | null };

export default function Offers() {
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const campaignIdFromUrl = searchParams.get("campaign_id");
  const [campaignId, setCampaignId] = useState(() => {
    const n = campaignIdFromUrl ? parseInt(campaignIdFromUrl, 10) : NaN;
    return Number.isFinite(n) && n > 0 ? n : 1;
  });
  useEffect(() => {
    const n = campaignIdFromUrl ? parseInt(campaignIdFromUrl, 10) : NaN;
    if (Number.isFinite(n) && n > 0 && n !== campaignId) setCampaignId(n);
  }, [campaignIdFromUrl]);
  const [modal, setModal] = useState<"create" | "edit" | "import" | null>(null);
  const [edit, setEdit] = useState<Offer | null>(null);
  const [form, setForm] = useState({ url: "", name: "", rate: "", amount: "", term: "", geo: "", device: "", priority: 0, is_active: true, description: "", restrictions: "", recommendations: "" });
  const [importUrl, setImportUrl] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [ocrStatus, setOcrStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [ocrProgress, setOcrProgress] = useState(0);
  const ocrInputRef = useRef<HTMLInputElement>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [applyDescModal, setApplyDescModal] = useState(false);
  const [applyDescForm, setApplyDescForm] = useState({ description: "", restrictions: "", recommendations: "" });
  const [applyDescToAll, setApplyDescToAll] = useState(false);

  useEffect(() => { setSelectedIds([]); }, [campaignId]);

  const { data: offers, isLoading } = useQuery({
    queryKey: ["offers", campaignId],
    queryFn: () => api.get("/offers/", { params: { campaign_id: campaignId } }).then((r) => r.data),
    enabled: !!campaignId,
  });
  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: crossCampaignSuggestions } = useQuery({
    queryKey: ["cross-campaign-offers", campaignId],
    queryFn: () => api.get("/analytics/cross-campaign-offer-suggestions", { params: { campaign_id: campaignId, days: 30, limit: 5 } }).then((r) => r.data),
    enabled: !!campaignId && campaignId > 0,
  });

  const createMut = useMutation({
    mutationFn: (d: typeof form & { campaign_id: number }) => api.post("/offers/", { ...d, campaign_id: campaignId, name: d.name || undefined, rate: d.rate || undefined, amount: d.amount || undefined, term: d.term || undefined, geo: d.geo || undefined, device: d.device || undefined, description: d.description || undefined, restrictions: d.restrictions || undefined, recommendations: d.recommendations || undefined }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["offers", campaignId] }); setModal(null); setForm({ url: "", name: "", rate: "", amount: "", term: "", geo: "", device: "", priority: 0, is_active: true, description: "", restrictions: "", recommendations: "" }); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<typeof form> }) => api.patch(`/offers/${id}`, { ...data, geo: data.geo || undefined, device: data.device || undefined, description: data.description ?? undefined, restrictions: data.restrictions ?? undefined, recommendations: data.recommendations ?? undefined }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["offers", campaignId] }); setModal(null); setEdit(null); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/offers/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["offers", campaignId] }),
  });
  const bulkDeleteMut = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(ids.map((id) => api.delete(`/offers/${id}`)));
      return ids.length;
    },
    onSuccess: (count) => {
      qc.invalidateQueries({ queryKey: ["offers", campaignId] });
      setSelectedIds([]);
      toast.success(`Удалено офферов: ${count}`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => {
      toast.error(e?.response?.data?.detail ?? "Ошибка удаления");
    },
  });
  const bulkApplyDescMut = useMutation({
    mutationFn: async ({ ids, data }: { ids: number[]; data: { description: string; restrictions: string; recommendations: string } }) => {
      await Promise.all(ids.map((id) => api.patch(`/offers/${id}`, { description: data.description || undefined, restrictions: data.restrictions || undefined, recommendations: data.recommendations || undefined })));
      return ids.length;
    },
    onSuccess: (count) => {
      qc.invalidateQueries({ queryKey: ["offers", campaignId] });
      setApplyDescModal(false);
      setApplyDescForm({ description: "", restrictions: "", recommendations: "" });
      setApplyDescToAll(false);
      toast.success(`Описание применено к ${count} офферам`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => {
      toast.error(e?.response?.data?.detail ?? "Ошибка");
    },
  });
  const importMut = useMutation({
    mutationFn: async () => {
      if (!importFile) throw new Error("Выберите файл CSV");
      const fd = new FormData();
      fd.append("campaign_id", String(campaignId));
      fd.append("offer_url", importUrl.trim());
      fd.append("file", importFile);
      const r = await api.post("/offers/import", fd, { headers: { "Content-Type": "multipart/form-data" } });
      return r.data as { imported: number };
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["offers", campaignId] });
      setImportUrl("");
      setImportFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setModal(null);
      alert(`Импортировано офферов: ${data.imported}`);
    },
    onError: (err: { response?: { data?: { detail?: string } } }) => {
      const msg = err.response?.data?.detail ?? (err instanceof Error ? err.message : "Ошибка импорта");
      alert(msg);
    },
  });

  const openEdit = (o: Offer) => {
    setEdit(o);
    setForm({ url: o.url, name: o.name ?? "", rate: o.rate ?? "", amount: o.amount ?? "", term: o.term ?? "", geo: o.geo ?? "", device: o.device ?? "", priority: o.priority, is_active: o.is_active, description: o.description ?? "", restrictions: o.restrictions ?? "", recommendations: o.recommendations ?? "" });
    setModal("edit");
  };

  const runOcr = async (file: File, onParsed?: (parsed: { description: string; restrictions: string; recommendations: string }) => void) => {
    setOcrStatus("loading");
    setOcrProgress(0);
    try {
      const { createWorker } = await import("tesseract.js");
      const worker = await createWorker("eng+rus", 1, {
        logger: (m: { progress?: number }) => setOcrProgress(Math.round((m?.progress ?? 0) * 100)),
      });
      const { data } = await worker.recognize(file);
      await worker.terminate();
      const parsed = parseOfferPageText(data.text);
      if (onParsed) {
        onParsed(parsed);
      } else {
        setForm((f) => ({
          ...f,
          description: parsed.description || f.description,
          restrictions: parsed.restrictions || f.restrictions,
          recommendations: parsed.recommendations || f.recommendations,
        }));
      }
      setOcrStatus("done");
    } catch (e) {
      setOcrStatus("error");
    }
    if (ocrInputRef.current) ocrInputRef.current.value = "";
  };

  useEffect(() => {
    if (modal !== "create" && modal !== "edit") return;
    const onPaste = (e: ClipboardEvent) => {
      const item = e.clipboardData?.items && Array.from(e.clipboardData.items).find((i) => i.type.startsWith("image/"));
      const file = item?.getAsFile();
      if (file) {
        e.preventDefault();
        runOcr(file);
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [modal]);

  useEffect(() => {
    if (!applyDescModal) return;
    const onPaste = (e: ClipboardEvent) => {
      const item = e.clipboardData?.items && Array.from(e.clipboardData.items).find((i) => i.type.startsWith("image/"));
      const file = item?.getAsFile();
      if (file) {
        e.preventDefault();
        runOcr(file, (parsed) => setApplyDescForm({ description: parsed.description, restrictions: parsed.restrictions, recommendations: parsed.recommendations }));
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [applyDescModal]);

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
        <button onClick={() => { setModal("create"); setForm({ url: "", name: "", rate: "", amount: "", term: "", geo: "", device: "", priority: 0, is_active: true, description: "", restrictions: "", recommendations: "" }); }} className="mt-6 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">Добавить оффер</button>
        <button onClick={() => { setModal("import"); setImportUrl(""); setImportFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; }} className="mt-6 px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg text-sm font-medium">Импорт из Zeydoo CSV</button>
        <button
          type="button"
          onClick={() => { setApplyDescToAll(true); setApplyDescForm({ description: "", restrictions: "", recommendations: "" }); setApplyDescModal(true); }}
          className="mt-6 px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium"
        >
          Условия для всех офферов кампании
        </button>
      </div>
      {crossCampaignSuggestions?.suggestions?.length > 0 && (
        <div className="mb-4 p-4 rounded-xl bg-violet-500/10 border border-violet-500/30">
          <h3 className="text-sm font-medium text-violet-200 mb-2">Офферы из других кампаний с хорошим ROI (за 30 дн.)</h3>
          <p className="text-slate-400 text-xs mb-2">Можно добавить похожий оффер в эту кампанию.</p>
          <ul className="space-y-1 text-sm">
            {(crossCampaignSuggestions.suggestions as { offer_id: number; campaign_id: number; url: string; geo?: string; name?: string; clicks: number; revenue: number; roi_per_click: number }[]).map((s) => (
              <li key={s.offer_id} className="flex flex-wrap items-center gap-2 text-slate-300">
                <span className="text-violet-300">#{s.offer_id}</span>
                {s.name && <span>{s.name}</span>}
                {s.geo && <span className="text-slate-500">({s.geo})</span>}
                <span>RPC: {s.roi_per_click}</span>
                <span className="text-slate-500">клики: {s.clicks}, выручка: {s.revenue}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {offers?.length ? (
            <>
              {selectedIds.length > 0 && (
                <div className="px-4 py-2 bg-slate-700/50 border-b border-slate-700 flex items-center gap-3 flex-wrap">
                  <span className="text-slate-300 text-sm">Выбрано: {selectedIds.length}</span>
                  <button
                    type="button"
                    onClick={() => {
                      if (window.confirm(`Удалить выбранные офферы (${selectedIds.length})?`)) bulkDeleteMut.mutate([...selectedIds]);
                    }}
                    disabled={bulkDeleteMut.isPending}
                    className="px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-white text-sm"
                  >
                    {bulkDeleteMut.isPending ? "Удаление…" : "Удалить выбранные"}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setApplyDescToAll(false); setApplyDescModal(true); }}
                    className="px-3 py-1.5 bg-violet-600 hover:bg-violet-500 rounded-lg text-white text-sm"
                  >
                    Применить описание к выбранным
                  </button>
                  <button type="button" onClick={() => setSelectedIds([])} className="text-slate-400 hover:text-white text-sm">Снять выделение</button>
                </div>
              )}
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium w-10">
                    <input
                      type="checkbox"
                      checked={offers.length > 0 && selectedIds.length === offers.length}
                      onChange={(e) => setSelectedIds(e.target.checked ? offers.map((o: Offer) => o.id) : [])}
                      className="rounded border-slate-500 bg-slate-700 text-emerald-500 focus:ring-emerald-500"
                    />
                  </th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Название</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Ставка</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Сумма</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Срок</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">URL</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Geo</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Device</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Приоритет</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Активен</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Условия</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {offers.map((o: Offer) => (
                  <tr key={o.id} className="border-b border-slate-700/50">
                    <td className="px-4 py-3 w-10">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(o.id)}
                        onChange={() => setSelectedIds((prev) => (prev.includes(o.id) ? prev.filter((id) => id !== o.id) : [...prev, o.id]))}
                        className="rounded border-slate-500 bg-slate-700 text-emerald-500 focus:ring-emerald-500"
                      />
                    </td>
                    <td className="px-4 py-3 text-white">{o.id}</td>
                    <td className="px-4 py-3 text-slate-300">{o.name ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{o.rate ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{o.amount ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{o.term ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400 truncate max-w-xs">{o.url}</td>
                    <td className="px-4 py-3 text-slate-400">{o.geo ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{o.device ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{o.priority}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs ${o.is_active ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-600 text-slate-400"}`}>{o.is_active ? "Да" : "Нет"}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {(o.description || o.restrictions || o.recommendations) ? <span className="text-emerald-400" title="Есть описание/ограничения/рекомендации">Есть</span> : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => openEdit(o)} className="text-emerald-400 hover:underline text-sm mr-2">Изменить</button>
                      <button onClick={() => window.confirm("Удалить?") && deleteMut.mutate(o.id)} disabled={deleteMut.isPending} className="text-red-400 hover:underline text-sm">Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </>
          ) : (
            <div className="p-8 text-center text-slate-400">Нет офферов для этой кампании</div>
          )}
        </div>
      )}

      {modal === "import" && createPortal(
        <div className="fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4" onClick={() => setModal(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4">Импорт из Zeydoo CSV</h2>
            <p className="text-slate-400 text-sm mb-4">Выгрузите оффер в Zeydoo (Export to CSV) и укажите трекинг-ссылку этого оффера — по каждой строке (гео) будет создан оффер в выбранной кампании.</p>
            <div className="space-y-3">
              <input type="url" value={importUrl} onChange={(e) => setImportUrl(e.target.value)} placeholder="URL оффера (трекинг-ссылка из Zeydoo)" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500" />
              <div>
                <input ref={fileInputRef} type="file" accept=".csv" onChange={(e) => setImportFile(e.target.files?.[0] ?? null)} className="hidden" />
                <button type="button" onClick={() => fileInputRef.current?.click()} className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm hover:bg-slate-600">{importFile ? importFile.name : "Выбрать CSV"}</button>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setModal(null)} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button onClick={() => importMut.mutate()} disabled={!importUrl.trim() || !importFile || importMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white">Импортировать</button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {modal && modal !== "import" && createPortal(
        <div className="fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4" onClick={() => { setModal(null); setEdit(null); }}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-2xl w-full max-h-[90vh] flex flex-col shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4 shrink-0">{modal === "create" ? "Новый оффер" : "Редактировать оффер"}</h2>
            <div className="space-y-3 overflow-y-auto min-h-0">
              <input value={form.url} onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))} placeholder="URL оффера (https://...)" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Название (для таблицы сравнения)" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <div className="grid grid-cols-3 gap-2">
                <input value={form.rate} onChange={(e) => setForm((f) => ({ ...f, rate: e.target.value }))} placeholder="Ставка" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} placeholder="Сумма" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.term} onChange={(e) => setForm((f) => ({ ...f, term: e.target.value }))} placeholder="Срок" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              </div>
              <input value={form.geo} onChange={(e) => setForm((f) => ({ ...f, geo: e.target.value }))} placeholder="Geo (RU, US...)" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input value={form.device} onChange={(e) => setForm((f) => ({ ...f, device: e.target.value }))} placeholder="Device (mobile, desktop...)" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <input type="number" value={form.priority} onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value) || 0 }))} placeholder="Приоритет" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              <label className="flex items-center gap-2 text-slate-300">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
                Активен
              </label>
              <p className="text-slate-500 text-xs mt-2">Полная картина оффера: вставьте текстом со страницы Zeydoo или загрузите скриншот / вставьте скриншот из буфера (Ctrl+V) — текст распознается и разойдётся по блокам.</p>
              <div className="flex items-center gap-3 flex-wrap">
                <input ref={ocrInputRef} type="file" accept="image/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) runOcr(f); }} />
                <button type="button" onClick={() => ocrInputRef.current?.click()} disabled={ocrStatus === "loading"} className="px-3 py-2 bg-slate-600 hover:bg-slate-500 disabled:opacity-50 rounded-lg text-white text-sm">
                  {ocrStatus === "loading" ? `Распознавание… ${ocrProgress}%` : "Распознать со скрина"}
                </button>
                <span className="text-slate-500 text-xs">или вставьте скриншот (Ctrl+V)</span>
                {ocrStatus === "done" && <span className="text-emerald-400 text-sm">Готово</span>}
                {ocrStatus === "error" && <span className="text-red-400 text-sm">Ошибка распознавания</span>}
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Description (описание, постбек, языки)</label>
                <textarea value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Текст из блока Description..." rows={2} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm resize-y" />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Restrictions (ограничения, тест-кап, запрещённые источники)</label>
                <textarea value={form.restrictions} onChange={(e) => setForm((f) => ({ ...f, restrictions: e.target.value }))} placeholder="Текст из блока Restrictions..." rows={2} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm resize-y" />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Our recommendations (рекомендации по трафику)</label>
                <textarea value={form.recommendations} onChange={(e) => setForm((f) => ({ ...f, recommendations: e.target.value }))} placeholder="Текст из блока Our recommendations..." rows={2} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm resize-y" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4 shrink-0">
              <button onClick={() => { setModal(null); setEdit(null); }} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button onClick={() => modal === "create" ? createMut.mutate({ ...form, campaign_id: campaignId }) : edit && updateMut.mutate({ id: edit.id, data: form })} disabled={!form.url || createMut.isPending || updateMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white">Сохранить</button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {applyDescModal && createPortal(
        <div className="fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4" onClick={() => { setApplyDescModal(false); setApplyDescToAll(false); }}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-2xl w-full max-h-[90vh] flex flex-col shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-2">{applyDescToAll ? `Применить описание ко всем офферам кампании` : `Применить описание к ${selectedIds.length} офферам`}</h2>
            <p className="text-slate-400 text-sm mb-4">Вставьте текст один раз — он будет записан во все выбранные офферы (описание, ограничения, рекомендации одинаковы для всех стран одного оффера).</p>
            <p className="text-slate-500 text-xs mb-2">Можно вставить скриншот страницы Zeydoo (Ctrl+V) — текст распознается и подставится в блоки. {ocrStatus === "loading" && <span className="text-amber-400">Распознавание… {ocrProgress}%</span>} {ocrStatus === "done" && <span className="text-emerald-400">Готово</span>}</p>
            <div className="space-y-3 overflow-y-auto min-h-0">
              <div>
                <label className="block text-slate-400 text-sm mb-1">Description (описание, постбек, языки)</label>
                <textarea value={applyDescForm.description} onChange={(e) => setApplyDescForm((f) => ({ ...f, description: e.target.value }))} placeholder="Текст из блока Description..." rows={3} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm resize-y" />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Restrictions (ограничения, тест-кап, запрещённые источники)</label>
                <textarea value={applyDescForm.restrictions} onChange={(e) => setApplyDescForm((f) => ({ ...f, restrictions: e.target.value }))} placeholder="Текст из блока Restrictions..." rows={3} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm resize-y" />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Our recommendations (рекомендации по трафику)</label>
                <textarea value={applyDescForm.recommendations} onChange={(e) => setApplyDescForm((f) => ({ ...f, recommendations: e.target.value }))} placeholder="Текст из блока Our recommendations..." rows={2} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm resize-y" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4 shrink-0">
              <button onClick={() => { setApplyDescModal(false); setApplyDescToAll(false); }} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button
                onClick={() => bulkApplyDescMut.mutate({ ids: applyDescToAll ? (offers ?? []).map((o: Offer) => o.id) : [...selectedIds], data: applyDescForm })}
                disabled={bulkApplyDescMut.isPending || (applyDescToAll ? !(offers?.length) : selectedIds.length === 0)}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg text-white"
              >
                {bulkApplyDescMut.isPending ? "Применяю…" : "Применить"}
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
