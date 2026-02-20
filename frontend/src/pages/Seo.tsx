import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";

export default function Seo() {
  const [campaignId, setCampaignId] = useState<number | null>(null);
  const [doorwayId, setDoorwayId] = useState<number | null>(null);
  const [suggestKeyword, setSuggestKeyword] = useState("");
  const [suggestRegion, setSuggestRegion] = useState("RU");

  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: doorways } = useQuery({
    queryKey: ["doorways", campaignId],
    queryFn: () => api.get("/doorways/", { params: campaignId ? { campaign_id: campaignId } : {} }).then((r) => r.data),
    enabled: !!campaignId,
  });
  const { data: cannibalization } = useQuery({
    queryKey: ["seo", "cannibalization", campaignId],
    queryFn: () => api.get(`/seo/cannibalization/${campaignId}`).then((r) => r.data),
    enabled: !!campaignId,
  });
  const { data: internalLinks } = useQuery({
    queryKey: ["seo", "internal-links", doorwayId],
    queryFn: () => api.get(`/seo/internal-links/${doorwayId}`).then((r) => r.data),
    enabled: !!doorwayId,
  });
  const { data: domains } = useQuery({
    queryKey: ["domains"],
    queryFn: () => api.get("/domains/").then((r) => r.data),
  });
  const [gscDomainId, setGscDomainId] = useState<number>(0);
  const [gscSiteUrl, setGscSiteUrl] = useState("");
  const [gscDays, setGscDays] = useState(28);
  const qc = useQueryClient();
  const gscFetchMut = useMutation({
    mutationFn: (d: { domain_id: number; site_url: string; days: number }) =>
      api.post("/indexing/gsc-fetch", d).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["analytics-summary"] });
      toast.success(`Импортировано: ${data.imported} записей`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e?.response?.data?.detail ?? "Ошибка GSC"),
  });
  const { data: domainSuggestions } = useQuery({
    queryKey: ["seo", "domains", suggestKeyword, suggestRegion],
    queryFn: () => api.get("/seo/domains/suggest", { params: { keyword: suggestKeyword, region: suggestRegion, count: 5 } }).then((r) => r.data),
    enabled: !!suggestKeyword.trim(),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">SEO</h1>
      <div className="space-y-6">
        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-medium text-white mb-4">GSC Fetch — импорт показов/кликов</h2>
          <p className="text-slate-400 text-sm mb-3">Загрузить impressions/clicks из Google Search Console в DoorwayMetrics. Нужны GSC credentials в Настройках.</p>
          <div className="flex gap-4 flex-wrap items-end mb-4">
            <div>
              <label className="block text-slate-400 text-xs mb-1">Домен</label>
              <select value={gscDomainId} onChange={(e) => setGscDomainId(Number(e.target.value))} className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-48">
                <option value={0}>—</option>
                {domains?.map((d: { id: number; domain: string }) => <option key={d.id} value={d.id}>{d.domain}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-slate-400 text-xs mb-1">GSC property (sc-domain:example.com)</label>
              <input value={gscSiteUrl} onChange={(e) => setGscSiteUrl(e.target.value)} placeholder="sc-domain:example.com" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-64" />
            </div>
            <div>
              <label className="block text-slate-400 text-xs mb-1">Дней</label>
              <input type="number" min={7} max={90} value={gscDays} onChange={(e) => setGscDays(Number(e.target.value) || 28)} className="w-20 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
            </div>
            <button onClick={() => gscFetchMut.mutate({ domain_id: gscDomainId, site_url: gscSiteUrl, days: gscDays })} disabled={!gscDomainId || !gscSiteUrl.trim() || gscFetchMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white text-sm">
              {gscFetchMut.isPending ? "Загрузка…" : "Импорт из GSC"}
            </button>
          </div>
        </div>
        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-medium text-white mb-4">Каннибализация ключевых слов</h2>
          <p className="text-slate-400 text-sm mb-3">Найти пересечения ключевых слов между дорвеями кампании.</p>
          <select
            value={campaignId ?? ""}
            onChange={(e) => setCampaignId(e.target.value ? Number(e.target.value) : null)}
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-64"
          >
            <option value="">— выбрать кампанию</option>
            {campaigns?.map((c: { id: number; name: string }) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          {cannibalization && (
            <pre className="mt-4 p-4 bg-slate-900 rounded-lg text-slate-300 text-sm overflow-auto max-h-64">{JSON.stringify(cannibalization, null, 2)}</pre>
          )}
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-medium text-white mb-4">Перелинковка (внутренние ссылки)</h2>
          <p className="text-slate-400 text-sm mb-3">Рекомендации по внутренним ссылкам для дорвея.</p>
          <div className="flex gap-4 mb-4">
            <select value={campaignId ?? ""} onChange={(e) => { setCampaignId(e.target.value ? Number(e.target.value) : null); setDoorwayId(null); }} className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-48">
              <option value="">— кампания</option>
              {campaigns?.map((c: { id: number; name: string }) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select value={doorwayId ?? ""} onChange={(e) => setDoorwayId(e.target.value ? Number(e.target.value) : null)} className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-64">
              <option value="">— дорвей</option>
              {doorways?.map((d: { id: number; path: string }) => <option key={d.id} value={d.id}>#{d.id} {d.path}</option>)}
            </select>
          </div>
          {internalLinks && (
            <pre className="p-4 bg-slate-900 rounded-lg text-slate-300 text-sm overflow-auto max-h-64">{JSON.stringify(internalLinks, null, 2)}</pre>
          )}
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-medium text-white mb-4">Подбор доменов</h2>
          <p className="text-slate-400 text-sm mb-3">AI-рекомендации доменов по ключевому слову.</p>
          <div className="flex gap-4 mb-4">
            <input value={suggestKeyword} onChange={(e) => setSuggestKeyword(e.target.value)} placeholder="Ключевое слово" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-64" />
            <input value={suggestRegion} onChange={(e) => setSuggestRegion(e.target.value)} placeholder="Регион (RU)" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white w-24" />
          </div>
          {domainSuggestions && (
            <pre className="p-4 bg-slate-900 rounded-lg text-slate-300 text-sm overflow-auto max-h-48">{JSON.stringify(domainSuggestions, null, 2)}</pre>
          )}
        </div>
      </div>
    </div>
  );
}
