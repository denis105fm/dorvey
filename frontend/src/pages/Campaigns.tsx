import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";

type Campaign = {
  id: number;
  name: string;
  affiliate_url?: string | null;
  language: string;
  locale: string;
  region: string;
  currency: string;
  status: string;
};

const COUNTRY_PRESETS: Record<string, { language: string; locale: string; region: string; currency: string }> = {
  RU: { language: "ru", locale: "ru-RU", region: "RU", currency: "RUB" },
  US: { language: "en", locale: "en-US", region: "US", currency: "USD" },
  KZ: { language: "ru", locale: "kk-KZ", region: "KZ", currency: "KZT" },
  BY: { language: "ru", locale: "be-BY", region: "BY", currency: "BYN" },
  UA: { language: "uk", locale: "uk-UA", region: "UA", currency: "UAH" },
  DE: { language: "de", locale: "de-DE", region: "DE", currency: "EUR" },
  GB: { language: "en", locale: "en-GB", region: "GB", currency: "GBP" },
  PL: { language: "pl", locale: "pl-PL", region: "PL", currency: "PLN" },
  FR: { language: "fr", locale: "fr-FR", region: "FR", currency: "EUR" },
  ES: { language: "es", locale: "es-ES", region: "ES", currency: "EUR" },
  IT: { language: "it", locale: "it-IT", region: "IT", currency: "EUR" },
};

export default function Campaigns() {
  const qc = useQueryClient();
  const [abCampaignId, setAbCampaignId] = useState<number | null>(null);
  const [rulesCampaignId, setRulesCampaignId] = useState<number | null>(null);
  const [conversionCampaignId, setConversionCampaignId] = useState<number | null>(null);
  const [trafficCampaignId, setTrafficCampaignId] = useState<number | null>(null);
  const [copyCampaignId, setCopyCampaignId] = useState<number | null>(null);
  const [copyCloakingCampaignId, setCopyCloakingCampaignId] = useState<number | null>(null);
  const [copyTargetId, setCopyTargetId] = useState<number>(0);
  const [copySourceId, setCopySourceId] = useState<number>(0);
  const [cloakingTargetId, setCloakingTargetId] = useState<number>(0);
  const [cloakingSourceId, setCloakingSourceId] = useState<number>(0);
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [edit, setEdit] = useState<Campaign | null>(null);
  const [form, setForm] = useState({ name: "", affiliate_url: "", language: "ru", locale: "ru-RU", region: "RU", currency: "RUB", status: "active" });
  const [convForm, setConvForm] = useState({
    urgency_text: "",
    social_stats: "",
    review1: "",
    review2: "",
    review3: "",
    exit_title: "",
    exit_cta: "",
    cta_desktop: "",
    cta_mobile: "",
  });

  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: abWinner, isLoading: abLoading } = useQuery({
    queryKey: ["ab-winner", abCampaignId],
    queryFn: () => api.get(`/optimizer/campaign/${abCampaignId}/ab-winner?days=14`).then((r) => r.data),
    enabled: !!abCampaignId,
  });
  const { data: trafficMix } = useQuery({
    queryKey: ["traffic-mix", trafficCampaignId],
    queryFn: () => api.get(`/optimizer/campaign/${trafficCampaignId}/traffic-mix?days=14`).then((r) => r.data),
    enabled: !!trafficCampaignId,
  });
  const { data: rules, isLoading: rulesLoading } = useQuery({
    queryKey: ["rules", rulesCampaignId],
    queryFn: () => api.get(`/rules/campaign/${rulesCampaignId}`).then((r) => r.data),
    enabled: !!rulesCampaignId,
  });
  const { data: conversion, isLoading: conversionLoading } = useQuery({
    queryKey: ["conversion", conversionCampaignId],
    queryFn: () => api.get(`/rules/campaign/${conversionCampaignId}/conversion`).then((r) => r.data),
    enabled: !!conversionCampaignId,
  });
  const selCamp = campaigns?.find((c: Campaign) => c.id === conversionCampaignId);
  const convLang = selCamp?.language || "ru";
  const [presetIndex, setPresetIndex] = useState(0);
  const { data: presets } = useQuery({
    queryKey: ["rules-presets", convLang, presetIndex],
    queryFn: () => api.get("/rules/presets", { params: { lang: convLang, index: presetIndex } }).then((r) => r.data),
    enabled: !!conversionCampaignId,
  });
  const { data: copyDoorways } = useQuery({
    queryKey: ["doorways", copyCampaignId],
    queryFn: () => api.get("/doorways/", { params: copyCampaignId ? { campaign_id: copyCampaignId } : {} }).then((r) => r.data),
    enabled: !!copyCampaignId,
  });
  const { data: cloakingDoorways } = useQuery({
    queryKey: ["doorways", copyCloakingCampaignId],
    queryFn: () => api.get("/doorways/", { params: copyCloakingCampaignId ? { campaign_id: copyCloakingCampaignId } : {} }).then((r) => r.data),
    enabled: !!copyCloakingCampaignId,
  });
  const copyWinnerMut = useMutation({
    mutationFn: (d: { source_doorway_id: number; target_doorway_id: number }) =>
      api.post(`/optimizer/campaign/${copyCampaignId}/copy-winner`, d).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success("Контент победителя скопирован");
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });
  const copyCloakingMut = useMutation({
    mutationFn: (d: { source_doorway_id: number; target_doorway_id: number }) =>
      api.post(`/optimizer/campaign/${copyCloakingCampaignId}/copy-cloaking-from-winner`, d).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      setCopyCloakingCampaignId(null);
      toast.success("Настройки (urgency, FAQ, CTA) скопированы");
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });

  const createMut = useMutation({
    mutationFn: (d: typeof form) => api.post("/campaigns/", d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campaigns"] }); setModal(null); setForm({ name: "", affiliate_url: "", language: "ru", locale: "ru-RU", region: "RU", currency: "RUB", status: "active" }); toast.success("Кампания создана"); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<typeof form> }) => api.patch(`/campaigns/${id}`, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campaigns"] }); setModal(null); setEdit(null); toast.success("Кампания обновлена"); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/campaigns/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["campaigns"] }); toast.success("Кампания удалена"); },
  });
  const updateRulesMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.put(`/rules/campaign/${rulesCampaignId}`, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules", rulesCampaignId] }); toast.success("Правила сохранены"); },
  });
  const setPreferredLayoutMut = useMutation({
    mutationFn: ({ campaignId, layoutIndex }: { campaignId: number; layoutIndex: number }) =>
      api.put(`/rules/campaign/${campaignId}`, { preferred_layout_index: layoutIndex }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["rules"] }); toast.success("Layout будет использоваться для новых дорвеев"); },
  });
  const updateConversionMut = useMutation({
    mutationFn: (data: Record<string, unknown>) => api.put(`/rules/campaign/${conversionCampaignId}/conversion`, data).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["conversion", conversionCampaignId] }); toast.success("Настройки конверсии сохранены"); },
  });

  useEffect(() => {
    if (!conversion) return;
    const u = conversion.urgency_block;
    const sp = conversion.social_proof;
    const ei = conversion.exit_intent;
    const cta = conversion.cta_by_device;
    setConvForm({
      urgency_text: typeof u === "string" ? u : (u?.text ?? ""),
      social_stats: typeof sp === "string" ? "" : (sp?.stats ?? ""),
      review1: (typeof sp !== "string" && sp?.reviews?.[0]) ?? "",
      review2: (typeof sp !== "string" && sp?.reviews?.[1]) ?? "",
      review3: (typeof sp !== "string" && sp?.reviews?.[2]) ?? "",
      exit_title: ei?.title ?? ei?.text ?? "",
      exit_cta: ei?.cta_text ?? ei?.cta ?? "",
      cta_desktop: cta?.desktop ?? "",
      cta_mobile: cta?.mobile ?? "",
    });
  }, [conversion]);

  const openEdit = (c: Campaign) => {
    setEdit(c);
    setForm({ name: c.name, affiliate_url: c.affiliate_url ?? "", language: c.language, locale: c.locale, region: c.region, currency: c.currency, status: c.status });
    setModal("edit");
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Кампании</h1>
        <button onClick={() => { setModal("create"); setForm({ name: "", affiliate_url: "", language: "ru", locale: "ru-RU", region: "RU", currency: "RUB", status: "active" }); }}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium">
          Добавить кампанию
        </button>
      </div>
      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="space-y-6">
          <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
            {campaigns?.length ? (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Название</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Язык</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Регион</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Статус</th>
                    <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c: Campaign) => (
                    <tr key={c.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-white">{c.id}</td>
                      <td className="px-4 py-3 text-white">{c.name}</td>
                      <td className="px-4 py-3 text-slate-400">{c.language}</td>
                      <td className="px-4 py-3 text-slate-400">{c.region}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400">{c.status}</span>
                      </td>
                      <td className="px-4 py-3 flex gap-2 flex-wrap">
                        <button onClick={() => setAbCampaignId(abCampaignId === c.id ? null : c.id)} className="text-amber-400 hover:underline text-sm">A/B</button>
                        <button onClick={() => setTrafficCampaignId(trafficCampaignId === c.id ? null : c.id)} className="text-blue-400 hover:underline text-sm">Traffic mix</button>
                        <button onClick={() => setCopyCampaignId(copyCampaignId === c.id ? null : c.id)} className="text-cyan-400 hover:underline text-sm">Copy winner</button>
                        <button onClick={() => setCopyCloakingCampaignId(copyCloakingCampaignId === c.id ? null : c.id)} className="text-orange-400 hover:underline text-sm">Копировать настройки</button>
                        <button onClick={() => setRulesCampaignId(rulesCampaignId === c.id ? null : c.id)} className="text-violet-400 hover:underline text-sm">Правила</button>
                        <button onClick={() => setConversionCampaignId(conversionCampaignId === c.id ? null : c.id)} className="text-amber-400 hover:underline text-sm">Конверсия</button>
                        <button onClick={() => openEdit(c)} className="text-emerald-400 hover:underline text-sm">Изменить</button>
                        <button onClick={() => window.confirm("Удалить?") && deleteMut.mutate(c.id)} disabled={deleteMut.isPending} className="text-red-400 hover:underline text-sm">Удалить</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-8 text-center text-slate-400">Пока нет кампаний</div>
            )}
          </div>
          {copyCloakingCampaignId && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">Скопировать настройки с победителя — кампания #{copyCloakingCampaignId}
                <button onClick={() => setCopyCloakingCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              <p className="text-slate-400 text-sm mb-3">Скопировать cloaking_rules (urgency, social proof, exit-intent, FAQ, CTA) с лучшего по CR дорвея.</p>
              <div className="flex gap-4 flex-wrap items-end">
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Источник (0 = авто по CR)</label>
                  <input type="number" min={0} value={cloakingSourceId} onChange={(e) => setCloakingSourceId(parseInt(e.target.value) || 0)} className="w-24 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Целевой дорвей</label>
                  <select value={cloakingTargetId} onChange={(e) => setCloakingTargetId(parseInt(e.target.value) || 0)} className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                    <option value={0}>—</option>
                    {cloakingDoorways?.map((d: { id: number; path: string }) => <option key={d.id} value={d.id}>#{d.id} {d.path}</option>)}
                  </select>
                </div>
                <button onClick={() => copyCloakingMut.mutate({ source_doorway_id: cloakingSourceId, target_doorway_id: cloakingTargetId })} disabled={!cloakingTargetId || copyCloakingMut.isPending} className="px-4 py-2 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 rounded-lg text-white text-sm">
                  {copyCloakingMut.isPending ? "Копирую…" : "Скопировать"}
                </button>
              </div>
            </div>
          )}
          {copyCampaignId && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">Копировать победителя — кампания #{copyCampaignId}
                <button onClick={() => setCopyCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              <p className="text-slate-400 text-sm mb-3">Скопировать контент (title, content, meta) с лучшего дорвея по CR на целевой.</p>
              <div className="flex gap-4 flex-wrap items-end">
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Источник (0 = авто по CR)</label>
                  <input type="number" min={0} value={copySourceId} onChange={(e) => setCopySourceId(parseInt(e.target.value) || 0)} className="w-24 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                </div>
                <div>
                  <label className="block text-slate-400 text-xs mb-1">Целевой дорвей</label>
                  <select value={copyTargetId} onChange={(e) => setCopyTargetId(parseInt(e.target.value) || 0)} className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                    <option value={0}>—</option>
                    {copyDoorways?.map((d: { id: number; path: string }) => <option key={d.id} value={d.id}>#{d.id} {d.path}</option>)}
                  </select>
                </div>
                <button onClick={() => copyWinnerMut.mutate({ source_doorway_id: copySourceId, target_doorway_id: copyTargetId })} disabled={!copyTargetId || copyWinnerMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white text-sm">
                  {copyWinnerMut.isPending ? "Копирую…" : "Скопировать"}
                </button>
              </div>
            </div>
          )}
          {abCampaignId && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">A/B Winner — кампания #{abCampaignId}
                <button onClick={() => setAbCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              {abLoading ? <p className="text-slate-400">Загрузка...</p> : abWinner && (
                <div className="space-y-2 text-slate-300 text-sm">
                  <p>{abWinner.message}</p>
                  {abWinner.winner !== null && (
                    <>
                      <p className="text-emerald-400">Лучший layout: {abWinner.winner} (CR: {abWinner.winner_cr}%, revenue: {abWinner.winner_revenue?.toFixed(2)})</p>
                      <button
                        onClick={() => abCampaignId != null && setPreferredLayoutMut.mutate({ campaignId: abCampaignId, layoutIndex: abWinner.winner })}
                        disabled={setPreferredLayoutMut.isPending}
                        className="px-3 py-1.5 bg-amber-600/80 hover:bg-amber-600 disabled:opacity-50 rounded-lg text-white text-sm"
                      >
                        Использовать для новых дорвеев
                      </button>
                    </>
                  )}
                  {abWinner.variants?.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {abWinner.variants.map((v: { layout_index: number; cr_percent: number; revenue: number; clicks: number; doorways_count: number }) => (
                        <li key={v.layout_index}>Layout {v.layout_index}: CR={v.cr_percent}%, revenue={v.revenue?.toFixed(2)}, клики={v.clicks}, дорвеев={v.doorways_count}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
          {trafficCampaignId && trafficMix && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">Traffic mix — кампания #{trafficCampaignId}
                <button onClick={() => setTrafficCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              <pre className="text-slate-300 text-sm overflow-auto">{JSON.stringify(trafficMix, null, 2)}</pre>
            </div>
          )}
          {conversionCampaignId && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">Конверсия — кампания #{conversionCampaignId}
                <button onClick={() => setConversionCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              <p className="text-slate-400 text-sm mb-4">Тексты для дорвеев кампании: urgency, social proof, exit-intent попап, CTA по устройству. Если не заданы — подставляются психологические шаблоны по умолчанию.</p>
              <div className="flex gap-2 mb-4">
                <button
                  onClick={() => {
                    if (!presets) return;
                    setConvForm({
                      urgency_text: presets.urgency_block?.text ?? "",
                      social_stats: presets.social_proof?.stats ?? "",
                      review1: (presets.social_proof?.reviews?.[0] as string) ?? "",
                      review2: (presets.social_proof?.reviews?.[1] as string) ?? "",
                      review3: (presets.social_proof?.reviews?.[2] as string) ?? "",
                      exit_title: presets.exit_intent?.title ?? "",
                      exit_cta: presets.exit_intent?.cta ?? "",
                      cta_desktop: presets.cta_by_device?.desktop ?? "",
                      cta_mobile: presets.cta_by_device?.mobile ?? "",
                    });
                  }}
                  disabled={!presets}
                  className="px-3 py-1.5 bg-violet-600/80 hover:bg-violet-600 disabled:opacity-50 rounded-lg text-white text-sm"
                >
                  Подставить шаблон #{presetIndex + 1}
                </button>
                <button
                  onClick={() => setPresetIndex((p) => (p + 1) % 6)}
                  className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 rounded-lg text-slate-300 text-sm"
                >
                  Другой вариант
                </button>
              </div>
              {conversionLoading ? (
                <p className="text-slate-400">Загрузка...</p>
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Urgency (жёлтый блок)</label>
                    <input value={convForm.urgency_text} onChange={(e) => setConvForm((f) => ({ ...f, urgency_text: e.target.value }))} placeholder="Одобрение за 5 минут • Без отказа" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500" />
                  </div>
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Social proof: статистика</label>
                    <input value={convForm.social_stats} onChange={(e) => setConvForm((f) => ({ ...f, social_stats: e.target.value }))} placeholder="12 450 заявок одобрено" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500" />
                  </div>
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Отзывы (до 3)</label>
                    <input value={convForm.review1} onChange={(e) => setConvForm((f) => ({ ...f, review1: e.target.value }))} placeholder="Отзыв 1" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white mb-1" />
                    <input value={convForm.review2} onChange={(e) => setConvForm((f) => ({ ...f, review2: e.target.value }))} placeholder="Отзыв 2" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white mb-1" />
                    <input value={convForm.review3} onChange={(e) => setConvForm((f) => ({ ...f, review3: e.target.value }))} placeholder="Отзыв 3" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Exit-intent: заголовок</label>
                    <input value={convForm.exit_title} onChange={(e) => setConvForm((f) => ({ ...f, exit_title: e.target.value }))} placeholder="Подождите! Специальное предложение" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Exit-intent: текст кнопки</label>
                    <input value={convForm.exit_cta} onChange={(e) => setConvForm((f) => ({ ...f, exit_cta: e.target.value }))} placeholder="Получить скидку" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-slate-400 text-sm mb-1">CTA desktop</label>
                      <input value={convForm.cta_desktop} onChange={(e) => setConvForm((f) => ({ ...f, cta_desktop: e.target.value }))} placeholder="Узнать подробнее" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                    </div>
                    <div>
                      <label className="block text-slate-400 text-sm mb-1">CTA mobile</label>
                      <input value={convForm.cta_mobile} onChange={(e) => setConvForm((f) => ({ ...f, cta_mobile: e.target.value }))} placeholder="Оформить заявку" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                    </div>
                  </div>
                  <button onClick={() => {
                    const payload: Record<string, unknown> = {};
                    if (convForm.urgency_text.trim()) payload.urgency_block = { text: convForm.urgency_text.trim() };
                    else payload.urgency_block = null;
                    const reviews = [convForm.review1, convForm.review2, convForm.review3].filter(Boolean);
                    if (convForm.social_stats.trim() || reviews.length) payload.social_proof = { stats: convForm.social_stats.trim() || undefined, reviews };
                    else payload.social_proof = null;
                    if (convForm.exit_title.trim() || convForm.exit_cta.trim()) payload.exit_intent = { title: convForm.exit_title.trim() || undefined, cta_text: convForm.exit_cta.trim() || undefined };
                    else payload.exit_intent = null;
                    if (convForm.cta_desktop.trim() || convForm.cta_mobile.trim()) payload.cta_by_device = { desktop: convForm.cta_desktop.trim() || undefined, mobile: convForm.cta_mobile.trim() || undefined };
                    else payload.cta_by_device = null;
                    updateConversionMut.mutate(payload);
                  }} disabled={updateConversionMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white text-sm">
                    {updateConversionMut.isPending ? "Сохранение…" : "Сохранить конверсию"}
                  </button>
                </div>
              )}
            </div>
          )}
          {rulesCampaignId && (
            <div className="p-5 bg-slate-800/80 rounded-xl border border-slate-700">
              <h2 className="text-lg font-medium text-white mb-3">Правила кампании #{rulesCampaignId}
                <button onClick={() => setRulesCampaignId(null)} className="ml-2 text-slate-400 hover:text-white text-sm">✕</button>
              </h2>
              {rulesLoading ? <p className="text-slate-400">Загрузка...</p> : rules && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Запрещённые слова (через запятую)</label>
                    <input value={(rules.forbidden_words || []).join(", ")} onChange={(e) => updateRulesMut.mutate({ forbidden_words: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Разрешённые GEO (через запятую)</label>
                    <input value={(rules.allowed_geo || []).join(", ")} onChange={(e) => updateRulesMut.mutate({ allowed_geo: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                      className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 text-slate-300">
                      <input type="checkbox" checked={rules.require_disclaimer ?? false} onChange={(e) => updateRulesMut.mutate({ require_disclaimer: e.target.checked })} />
                      Disclaimer обязателен
                    </label>
                    <label className="flex items-center gap-2 text-slate-300">
                      <input type="checkbox" checked={rules.auto_switch_on_cr_drop ?? false} onChange={(e) => updateRulesMut.mutate({ auto_switch_on_cr_drop: e.target.checked })} />
                      Автосмена оффера при падении CR
                    </label>
                    <label className="flex items-center gap-2 text-slate-300">
                      <input type="checkbox" checked={rules.auto_rollback_on_cr_drop ?? false} onChange={(e) => updateRulesMut.mutate({ auto_rollback_on_cr_drop: e.target.checked })} />
                      Автооткат при падении CR
                    </label>
                    <label className="flex items-center gap-2 text-slate-300" title="Бот видит SEO-версию, человек — конверсионную. Нужен Nginx map по User-Agent.">
                      <input type="checkbox" checked={rules.cloaking_enabled ?? false} onChange={(e) => updateRulesMut.mutate({ cloaking_enabled: e.target.checked })} />
                      Cloaking (бот / человек)
                    </label>
                  </div>
                  {rules.cloaking_enabled && (
                    <div>
                      <label className="block text-slate-400 text-sm mb-1">User-Agent для ботов (через запятую, для Nginx)</label>
                      <input
                        value={Array.isArray(rules.cloaking_bot_patterns) ? rules.cloaking_bot_patterns.join(", ") : (rules.cloaking_bot_patterns ?? "Googlebot, YandexBot, bingbot").toString()}
                        onChange={(e) => updateRulesMut.mutate({ cloaking_bot_patterns: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                        placeholder="Googlebot, YandexBot, bingbot"
                        className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
                      />
                    </div>
                  )}
                  <div>
                    <label className="block text-slate-400 text-sm mb-1">Порог отката (% падения CR)</label>
                    <input type="number" value={rules.rollback_threshold_percent ?? 15} onChange={(e) => updateRulesMut.mutate({ rollback_threshold_percent: parseFloat(e.target.value) || 15 })}
                      className="w-32 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  </div>
                  {(rules.preferred_layout_index !== undefined && rules.preferred_layout_index !== null) && (
                    <p className="text-slate-400 text-sm">
                      Layout для новых дорвеев: <span className="text-amber-400">{rules.preferred_layout_index}</span>
                      <button type="button" onClick={() => updateRulesMut.mutate({ preferred_layout_index: null })} className="ml-2 text-slate-500 hover:text-white text-xs">Сбросить</button>
                    </p>
                  )}
                  <div className="border-t border-slate-600 pt-3 mt-3">
                    <h3 className="text-slate-300 font-medium mb-2">Авто-применение рекомендаций AI</h3>
                    <p className="text-slate-400 text-xs mb-2">Cron при CR/CTR ниже порога вызывает AI-рекомендации и применяет первую (title/meta/content). Нужен OpenAI в Настройках. Ключ: <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">platform.openai.com/api-keys</a>.</p>
                    <label className="flex items-center gap-2 text-slate-300 mb-3">
                      <input type="checkbox" checked={rules.auto_apply_recommendations ?? false} onChange={(e) => updateRulesMut.mutate({ auto_apply_recommendations: e.target.checked })} />
                      Включить авто-применение
                    </label>
                    {(rules.auto_apply_recommendations ?? false) && (
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">Порог CR (%) — применять если ниже</label>
                          <input type="number" step={0.1} value={rules.auto_apply_cr_threshold_percent ?? 1.5} onChange={(e) => updateRulesMut.mutate({ auto_apply_cr_threshold_percent: parseFloat(e.target.value) || 1.5 })} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        </div>
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">Порог CTR (%) — применять если ниже</label>
                          <input type="number" step={0.1} value={rules.auto_apply_ctr_threshold_percent ?? 2} onChange={(e) => updateRulesMut.mutate({ auto_apply_ctr_threshold_percent: parseFloat(e.target.value) || 2 })} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        </div>
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">Мин. кликов за период</label>
                          <input type="number" value={rules.auto_apply_min_clicks ?? 30} onChange={(e) => updateRulesMut.mutate({ auto_apply_min_clicks: parseInt(e.target.value) || 30 })} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        </div>
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">Мин. показов</label>
                          <input type="number" value={rules.auto_apply_min_impressions ?? 100} onChange={(e) => updateRulesMut.mutate({ auto_apply_min_impressions: parseInt(e.target.value) || 100 })} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="border-t border-slate-600 pt-3 mt-3">
                    <h3 className="text-slate-300 font-medium mb-2">Ранний стоп (прибыль на 2–3 день)</h3>
                    <p className="text-slate-400 text-xs mb-2">Автопауза дорвеев, задеплоенных недавно: есть трафик, но 0 конверсий. Крон run-all вызывает это правило.</p>
                    <label className="flex items-center gap-2 text-slate-300 mb-3">
                      <input type="checkbox" checked={rules.early_pause_enabled !== false} onChange={(e) => updateRulesMut.mutate({ early_pause_enabled: e.target.checked })} />
                      Включить ранний стоп
                    </label>
                    {(rules.early_pause_enabled !== false) && (
                      <div className="grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">Период (дней) — дорвеи задеплоены за</label>
                          <input type="number" min={1} max={7} value={rules.early_pause_min_days ?? 2} onChange={(e) => updateRulesMut.mutate({ early_pause_min_days: parseInt(e.target.value) || 2 })} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        </div>
                        <div>
                          <label className="block text-slate-400 text-xs mb-1">Мин. кликов — паузить если 0 конверсий при ≥</label>
                          <input type="number" min={10} max={200} value={rules.early_pause_min_clicks ?? 30} onChange={(e) => updateRulesMut.mutate({ early_pause_min_clicks: parseInt(e.target.value) || 30 })} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {modal && createPortal(
        <div className="fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4" onClick={() => { setModal(null); setEdit(null); }}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full max-h-[90vh] flex flex-col shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4 shrink-0">{modal === "create" ? "Новая кампания" : "Редактировать кампанию"}</h2>
            <div className="space-y-3 overflow-y-auto min-h-0">
              <div>
                <label className="block text-slate-400 text-sm mb-1">Название <span className="text-amber-400">*</span></label>
                <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Например: Click Box US" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Affiliate URL</label>
                <input value={form.affiliate_url} onChange={(e) => setForm((f) => ({ ...f, affiliate_url: e.target.value }))} placeholder="https://..." className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Страна / регион</label>
                <select
                  value={Object.keys(COUNTRY_PRESETS).find((k) => COUNTRY_PRESETS[k].region === form.region && COUNTRY_PRESETS[k].locale === form.locale) ?? ""}
                  onChange={(e) => {
                    const key = e.target.value as keyof typeof COUNTRY_PRESETS;
                    if (key && COUNTRY_PRESETS[key]) setForm((f) => ({ ...f, ...COUNTRY_PRESETS[key] }));
                  }}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                >
                  <option value="">— свои значения</option>
                  {Object.entries(COUNTRY_PRESETS).map(([code, p]) => (
                    <option key={code} value={code}>{p.region} — {p.language}, {p.currency}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <input value={form.language} onChange={(e) => setForm((f) => ({ ...f, language: e.target.value }))} placeholder="Язык" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.region} onChange={(e) => setForm((f) => ({ ...f, region: e.target.value }))} placeholder="Регион" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.locale} onChange={(e) => setForm((f) => ({ ...f, locale: e.target.value }))} placeholder="Locale" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <input value={form.currency} onChange={(e) => setForm((f) => ({ ...f, currency: e.target.value }))} placeholder="Валюта" className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
              </div>
              <p className="text-slate-500 text-xs">Для целевой страны в поиске укажите ту же страну в GSC (International Targeting) и выберите соответствующий регион (напр. US, RU).</p>
              <select value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white">
                <option value="active">active</option>
                <option value="paused">paused</option>
              </select>
            </div>
            <div className="flex justify-end gap-2 mt-4 shrink-0">
              <button onClick={() => { setModal(null); setEdit(null); }} className="px-4 py-2 bg-slate-600 rounded-lg text-white">Отмена</button>
              <button onClick={() => modal === "create" ? createMut.mutate(form) : edit && updateMut.mutate({ id: edit.id, data: form })} disabled={!form.name || createMut.isPending || updateMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-white">Сохранить</button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
