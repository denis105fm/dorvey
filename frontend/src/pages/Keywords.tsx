import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";

export default function Keywords() {
  const qc = useQueryClient();
  const [campaignId, setCampaignId] = useState(1);
  const [volume, setVolume] = useState(0);
  const [suggestSeed, setSuggestSeed] = useState("");
  const [suggestCountry, setSuggestCountry] = useState("RU");
  const [selectedSuggest, setSelectedSuggest] = useState<{ keyword: string; volume: number; cpc: number }[]>([]);
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

  const { data: offerGeos } = useQuery({
    queryKey: ["keywords", "offer-geos", campaignId],
    queryFn: () => api.get("/keywords/suggest-by-offers-geo", { params: { campaign_id: campaignId } }).then((r) => r.data),
    enabled: !!campaignId,
  });

  const suggestMut = useMutation({
    mutationFn: (d: { campaign_id: number; seed: string; country: string; limit: number }) =>
      api.post("/keywords/suggest-from-external", d).then((r) => r.data),
    onSuccess: () => { setSelectedSuggest([]); },
  });

  const suggestByOffersMut = useMutation({
    mutationFn: (d: { campaign_id: number; seed: string; limit: number }) =>
      api.post("/keywords/suggest-by-offers-geo-batch", { ...d, country: "RU" }).then((r) => r.data),
    onSuccess: () => { setSelectedSuggest([]); },
  });

  const importSuggestMut = useMutation({
    mutationFn: (d: { campaign_id: number; items: { keyword: string; volume: number; cpc: number }[]; region?: string; source?: string }) =>
      api.post("/keywords/bulk-import-from-suggest", d).then((r) => r.data),
    onSuccess: (_, v) => {
      qc.invalidateQueries({ queryKey: ["keywords", campaignId] });
      setSelectedSuggest([]);
      toast.success(`Импортировано ${v.items.length} ключей`);
    },
  });

  const bulkMut = useMutation({
    mutationFn: (data: { campaign_id: number; keywords: string[]; volume: number }) => api.post("/keywords/bulk", data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["keywords", campaignId] }); fileRef.current && (fileRef.current.value = ""); },
  });

  const { data: startupNiches } = useQuery({
    queryKey: ["keywords", "startup-niches"],
    queryFn: () => api.get("/keywords/startup-niches").then((r) => r.data),
  });

  const startupKwMut = useMutation({
    mutationFn: (d: { seeds: string[]; country: string; limit_per_seed: number; campaign_id?: number; auto_import: boolean }) =>
      api.post("/keywords/startup-keywords", d).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["keywords", campaignId] });
      toast.success(data.imported ? `Подтянуто ключей: ${data.keywords?.length ?? 0}, импортировано: ${data.imported}` : `Подтянуто ключей: ${data.keywords?.length ?? 0}`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });

  const autoPullMut = useMutation({
    mutationFn: (d: { campaign_id: number; seed: string; country: string; limit: number }) =>
      api.post("/keywords/auto-pull-and-import", d).then((r) => r.data),
    onSuccess: (data: { imported: number; source?: string; hint?: string; debug?: Record<string, unknown> }) => {
      qc.invalidateQueries({ queryKey: ["keywords", campaignId] });
      if (data.imported > 0) {
        toast.success(`Авто-импорт: добавлено ${data.imported} ключей (${data.source})`);
      } else if (data.hint) {
        toast.warning(data.hint);
        if (data.debug) console.warn("Провайдер подсказок (debug):", data.debug);
      } else {
        toast.info(`Авто-импорт: добавлено 0 ключей (${data.source})`);
      }
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });

  const [startupSeeds, setStartupSeeds] = useState<string[]>([]);
  const [autoPullSeed, setAutoPullSeed] = useState("");

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

      <div className="mb-6 p-4 rounded-xl border border-slate-600 bg-slate-800/50">
        <h2 className="text-lg font-medium text-white mb-3">Подтянуть из внешних источников</h2>
        <p className="text-slate-400 text-sm mb-3">Ключи с объёмом по гео. Выберите провайдера (DataForSeo, FetchSERP или Google Ads API) в <a href="/settings" className="text-emerald-400 hover:underline">Настройках → Интеграции</a>. Регистрация: <a href="https://app.dataforseo.com/register" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">DataForSeo</a>, <a href="https://www.fetchserp.com/app" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">FetchSERP</a>, <a href="https://ads.google.com/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Google Ads</a>.</p>
        <div className="flex flex-wrap items-end gap-3 mb-3">
          <div>
            <label className="block text-slate-400 text-xs mb-1">Стартовый запрос (seed)</label>
            <input
              value={suggestSeed}
              onChange={(e) => setSuggestSeed(e.target.value)}
              placeholder="кредит наличными"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-56"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-xs mb-1">Страна (geo)</label>
            <select
              value={suggestCountry}
              onChange={(e) => setSuggestCountry(e.target.value)}
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
            >
              {offerGeos?.geos?.length ? offerGeos.geos.map((g: string) => <option key={g} value={g}>{g} (офферы)</option>) : null}
              <option value="RU">RU</option>
              <option value="US">US</option>
              <option value="KZ">KZ</option>
              <option value="BY">BY</option>
              <option value="UA">UA</option>
              <option value="DE">DE</option>
            </select>
          </div>
          <button
            onClick={() => suggestMut.mutate({ campaign_id: campaignId, seed: suggestSeed, country: suggestCountry, limit: 50 })}
            disabled={!suggestSeed.trim() || suggestMut.isPending}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg text-sm"
          >
            {suggestMut.isPending ? "Загрузка…" : "Подтянуть"}
          </button>
          <button
            onClick={() => suggestByOffersMut.mutate({ campaign_id: campaignId, seed: suggestSeed, limit: 80 })}
            disabled={!suggestSeed.trim() || suggestByOffersMut.isPending || !offerGeos?.geos?.length}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg text-sm"
            title="Подтянуть по гео офферов кампании"
          >
            {suggestByOffersMut.isPending ? "Загрузка…" : "По гео офферов"}
          </button>
        </div>
        {(suggestMut.data?.keywords?.length || suggestByOffersMut.data?.keywords?.length) ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-sm">Выберите ключи для импорта (сортировка по объёму):</span>
              <button
                onClick={() => importSuggestMut.mutate({
                  campaign_id: campaignId,
                  items: selectedSuggest,
                  region: (suggestByOffersMut.data ? undefined : suggestCountry),
                  source: (suggestMut.data || suggestByOffersMut.data)?.source,
                })}
                disabled={selectedSuggest.length === 0 || importSuggestMut.isPending}
                className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded text-sm"
              >
                Импортировать выбранные ({selectedSuggest.length})
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto border border-slate-600 rounded-lg p-2 space-y-1">
              {(suggestMut.data || suggestByOffersMut.data)?.keywords?.slice(0, 80).map((kw: { keyword: string; volume: number; cpc: number }, i: number) => (
                <label key={i} className="flex items-center gap-3 cursor-pointer hover:bg-slate-700/50 rounded px-2 py-1">
                  <input
                    type="checkbox"
                    checked={selectedSuggest.some((s) => s.keyword === kw.keyword)}
                    onChange={(e) => {
                      if (e.target.checked) setSelectedSuggest((prev) => [...prev, kw]);
                      else setSelectedSuggest((prev) => prev.filter((s) => s.keyword !== kw.keyword));
                    }}
                    className="rounded border-slate-600 text-violet-600"
                  />
                  <span className="text-white flex-1">{kw.keyword}</span>
                  <span className="text-slate-400 text-sm">{kw.volume} запросов/мес</span>
                </label>
              ))}
            </div>
          </div>
        ) : (suggestMut.isError || suggestByOffersMut.isError) ? (
          <p className="text-amber-400 text-sm">
            {((suggestMut.error || suggestByOffersMut.error) as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Ошибка. Выберите провайдера подсказки ключей в Настройках → Интеграции и укажите API данные."}
          </p>
        ) : null}
      </div>

      <div className="mb-6 p-4 rounded-xl border border-slate-600 bg-slate-800/50">
        <h2 className="text-lg font-medium text-white mb-2">Стартовый набор ниш</h2>
        <p className="text-slate-400 text-sm mb-3">Подтянуть ключи по готовым нишам из справочника. Можно сразу импортировать в кампанию.</p>
        {startupNiches?.niches?.length ? (
          <div className="flex flex-wrap gap-2 mb-3">
            {startupNiches.niches.map((n: { id: string; name: string; seeds: string[] }) => {
              const isSelected = n.seeds.some((s) => startupSeeds.includes(s));
              return (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => setStartupSeeds((prev) => isSelected ? prev.filter((s) => !n.seeds.includes(s)) : [...prev, ...n.seeds])}
                  className={`px-3 py-1.5 rounded-lg text-sm ${isSelected ? "bg-violet-600 text-white" : "bg-slate-700 text-slate-300 hover:bg-slate-600"}`}
                >
                  {n.name}
                </button>
              );
            })}
          </div>
        ) : null}
        <div className="flex flex-wrap items-end gap-2">
          <input
            value={startupSeeds.join(", ")}
            onChange={(e) => setStartupSeeds(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
            placeholder="Или введите seed-фразы через запятую"
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-72"
          />
          <select
            value={suggestCountry}
            onChange={(e) => setSuggestCountry(e.target.value)}
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
          >
            <option value="RU">RU</option>
            <option value="US">US</option>
            <option value="KZ">KZ</option>
          </select>
          <button
            onClick={() => startupKwMut.mutate({ seeds: startupSeeds.length ? startupSeeds : ["займ на карту"], country: suggestCountry, limit_per_seed: 25, auto_import: false })}
            disabled={startupKwMut.isPending}
            className="px-4 py-2 bg-slate-600 hover:bg-slate-500 text-white rounded-lg text-sm"
          >
            {startupKwMut.isPending ? "…" : "Только подтянуть"}
          </button>
          <button
            onClick={() => startupKwMut.mutate({ seeds: startupSeeds.length ? startupSeeds : ["займ на карту"], country: suggestCountry, limit_per_seed: 25, campaign_id: campaignId, auto_import: true })}
            disabled={startupKwMut.isPending}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm"
          >
            {startupKwMut.isPending ? "…" : "Подтянуть и импортировать"}
          </button>
        </div>
      </div>

      <div className="mb-6 p-4 rounded-xl border border-slate-600 bg-slate-800/50">
        <h2 className="text-lg font-medium text-white mb-2">Авто-подтянуть ключи</h2>
        <p className="text-slate-400 text-sm mb-3">Система сама подтянет ключи из выбранного провайдера и сразу добавит их в кампанию (без ручного выбора).</p>
        <div className="flex flex-wrap items-end gap-2">
          <input
            value={autoPullSeed}
            onChange={(e) => setAutoPullSeed(e.target.value)}
            placeholder="Стартовая фраза (seed)"
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-48"
          />
          <select
            value={suggestCountry}
            onChange={(e) => setSuggestCountry(e.target.value)}
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
          >
            <option value="RU">RU</option>
            <option value="US">US</option>
          </select>
          <button
            onClick={() => autoPullMut.mutate({ campaign_id: campaignId, seed: autoPullSeed || suggestSeed || "займ", country: suggestCountry, limit: 40 })}
            disabled={autoPullMut.isPending}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm"
          >
            {autoPullMut.isPending ? "Загрузка…" : "Подтянуть и импортировать"}
          </button>
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
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Гео</th>
                </tr>
              </thead>
              <tbody>
                {keywords.map((k: { id: number; keyword: string; cluster_id: number | null; volume: number; region?: string }) => (
                  <tr key={k.id} className="border-b border-slate-700/50">
                    <td className="px-4 py-3 text-white">{k.id}</td>
                    <td className="px-4 py-3 text-white">{k.keyword}</td>
                    <td className="px-4 py-3 text-slate-400">{k.cluster_id ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-400">{k.volume}</td>
                    <td className="px-4 py-3 text-slate-400">{k.region ?? "—"}</td>
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
