import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import api from "../api/client";
import { Webhook, Settings as SettingsIcon, Send, Search, Shield, BarChart3, MousePointer, Palette, Bot, CreditCard, Smartphone, CheckCircle, Eye, EyeOff } from "lucide-react";

type IntegrationsData = {
  openai_api_key?: string | null;
  telegram_bot_token?: string | null;
  telegram_chat_id?: string | null;
  gsc_client_id?: string | null;
  gsc_client_secret?: string | null;
  gsc_refresh_token?: string | null;
  bing_api_key?: string | null;
  ssl_auto_enabled?: boolean | null;
  voluum_api_key?: string | null;
  voluum_api_url?: string | null;
  binom_api_key?: string | null;
  binom_api_url?: string | null;
  hotjar_site_id?: string | null;
  clarity_project_id?: string | null;
  exit_intent_enabled?: boolean | null;
  trust_elements_enabled?: boolean | null;
  click_tracking_enabled?: boolean | null;
  api_base_url?: string | null;
  visitor_capture_enabled?: boolean | null;
  email_capture_enabled?: boolean | null;
  vapid_public_key?: string | null;
  vapid_private_key?: string | null;
  slack_webhook_url?: string | null;
  email_notifications_enabled?: boolean | null;
  facebook_pixel_id?: string | null;
  google_ads_id?: string | null;
  min_clicks_for_profit?: number | null;
  news_api_key?: string | null;
  gnews_api_key?: string | null;
  mediastack_api_key?: string | null;
  guardian_api_key?: string | null;
  external_data_enabled?: boolean | null;
  seasonality_data_url?: string | null;
  dataforseo_login?: string | null;
  dataforseo_password?: string | null;
  keyword_provider?: string | null;
  fetchserp_api_key?: string | null;
  google_ads_developer_token?: string | null;
  google_ads_client_id?: string | null;
  google_ads_client_secret?: string | null;
  google_ads_refresh_token?: string | null;
  google_ads_customer_id?: string | null;
  google_ads_manager_customer_id?: string | null;
};

/** Секретные поля интеграций: не отправляем при сохранении, если пользователь их не редактировал (защита от перезаписи автозаполнением/маской). */
const SENSITIVE_INTEGRATION_KEYS = new Set([
  "openai_api_key",
  "telegram_bot_token", "telegram_chat_id",
  "gsc_client_id", "gsc_client_secret", "gsc_refresh_token",
  "bing_api_key",
  "news_api_key", "gnews_api_key", "mediastack_api_key", "guardian_api_key",
  "dataforseo_login", "dataforseo_password",
  "fetchserp_api_key",
  "google_ads_developer_token", "google_ads_client_id", "google_ads_client_secret",
  "google_ads_refresh_token", "google_ads_customer_id", "google_ads_manager_customer_id",
  "voluum_api_key", "voluum_api_url", "binom_api_key", "binom_api_url",
  "slack_webhook_url",
  "vapid_private_key", "vapid_public_key",
  "hotjar_site_id", "clarity_project_id",
  "facebook_pixel_id", "google_ads_id",
]);

const WEBHOOK_EVENT_OPTIONS: { value: string; label: string }[] = [
  { value: "doorway.deployed", label: "Деплой дорвея" },
  { value: "doorway.conversion", label: "Конверсия" },
  { value: "doorway.rollback", label: "Откат" },
  { value: "doorway.anomaly", label: "Аномалия (падение CR)" },
  { value: "doorway.auto_paused", label: "Авто-пауза (убыточный / ранний стоп 2–3 дн.)" },
  { value: "doorway.auto_fix", label: "Авто-применение рекомендации" },
  { value: "billing.near_limit", label: "Лимит ≈80%" },
  { value: "billing.over_limit", label: "Превышен лимит" },
];

export default function Settings() {
  const qc = useQueryClient();
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEvents, setWebhookEvents] = useState<string[]>(["doorway.deployed", "doorway.conversion", "doorway.auto_paused"]);

  const toggleWebhookEvent = (event: string) => {
    setWebhookEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  const [integrations, setIntegrations] = useState<IntegrationsData>({});
  const [whitelabel, setWhitelabel] = useState<{
    brand_name?: string;
    logo_url?: string;
    primary_color?: string;
    favicon_url?: string;
  }>({});
  const [openaiTestStatus, setOpenaiTestStatus] = useState<null | "checking" | "ok" | "error">(null);
  const [openaiTestMessage, setOpenaiTestMessage] = useState("");
  const [fetchserpTestStatus, setFetchserpTestStatus] = useState<null | "checking" | "ok" | "error">(null);
  const [fetchserpTestMessage, setFetchserpTestMessage] = useState("");
  const [bingTestStatus, setBingTestStatus] = useState<null | "checking" | "ok" | "error">(null);
  const [bingTestMessage, setBingTestMessage] = useState("");
  const [clarityTestStatus, setClarityTestStatus] = useState<null | "checking" | "ok" | "error">(null);
  const [clarityTestMessage, setClarityTestMessage] = useState("");
  const [hotjarTestStatus, setHotjarTestStatus] = useState<null | "checking" | "ok" | "error">(null);
  const [hotjarTestMessage, setHotjarTestMessage] = useState("");
  const [googleAdsTestStatus, setGoogleAdsTestStatus] = useState<null | "checking" | "ok" | "error">(null);
  const [googleAdsTestMessage, setGoogleAdsTestMessage] = useState("");
  const [googleAdsCreateTestLoading, setGoogleAdsCreateTestLoading] = useState(false);
  const [showGoogleAdsDevToken, setShowGoogleAdsDevToken] = useState(false);
  const [showGoogleAdsSecret, setShowGoogleAdsSecret] = useState(false);
  const [showGoogleAdsRefresh, setShowGoogleAdsRefresh] = useState(false);
  const googleAdsPopupRef = useRef<Window | null>(null);
  const [googleAdsRedirectUri, setGoogleAdsRedirectUri] = useState<string | null>(null);
  /** Какие секретные поля пользователь редактировал — при сохранении не отправляем нередактированные (защита от перезаписи). */
  const editedSensitiveRef = useRef<Set<string>>(new Set());
  const markSensitiveEdited = (key: keyof IntegrationsData) => {
    editedSensitiveRef.current = new Set(editedSensitiveRef.current).add(key as string);
  };
  const { data: integrationsData } = useQuery({
    queryKey: ["settings", "integrations"],
    queryFn: () => api.get<IntegrationsData>("/settings/integrations/all").then((r) => r.data),
  });
  const { data: whitelabelData } = useQuery({
    queryKey: ["settings", "whitelabel"],
    queryFn: () => api.get("/settings/whitelabel").then((r) => r.data),
  });
  useEffect(() => {
    if (integrationsData) {
      setIntegrations(integrationsData);
      editedSensitiveRef.current = new Set();
    }
  }, [integrationsData]);
  useEffect(() => {
    if (whitelabelData) setWhitelabel(whitelabelData);
  }, [whitelabelData]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const gsc = params.get("gsc_token");
    if (gsc === "ok") {
      toast.success("Refresh Token получен и сохранён");
      qc.invalidateQueries({ queryKey: ["settings", "integrations"] });
      window.history.replaceState({}, "", window.location.pathname);
    } else if (gsc === "error") {
      toast.error(params.get("message") || "Не удалось получить Refresh Token");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [qc]);

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.data?.type === "google_ads_refresh_saved") {
        toast.success("Refresh token сохранён");
        qc.invalidateQueries({ queryKey: ["settings", "integrations"] });
        if (googleAdsPopupRef.current) try { googleAdsPopupRef.current.close(); } catch (_) {}
      } else if (e.data?.type === "google_ads_refresh_error") {
        toast.error("Не удалось получить refresh token");
        if (googleAdsPopupRef.current) try { googleAdsPopupRef.current.close(); } catch (_) {}
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [qc]);

  const saveIntegrationsMut = useMutation({
    mutationFn: (d: IntegrationsData) => {
      const payload = { ...d };
      SENSITIVE_INTEGRATION_KEYS.forEach((key) => {
        if (!editedSensitiveRef.current.has(key)) delete payload[key as keyof IntegrationsData];
      });
      return api.put("/settings/integrations/all", payload).then((r) => r.data);
    },
    onSuccess: (data: { openai_key_skipped?: boolean }) => {
      qc.invalidateQueries({ queryKey: ["settings", "integrations"] });
      toast.success("Интеграции сохранены");
      if (data?.openai_key_skipped) {
        toast.warning("Ключ OpenAI не изменён: в поле было короткое значение (возможная обрезка). Вставьте ключ целиком заново и сохраните.");
      }
    },
  });
  const saveWhitelabelMut = useMutation({
    mutationFn: (d: typeof whitelabel) => api.put("/settings/whitelabel", d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["settings", "whitelabel"] }); toast.success("Брендинг сохранён"); },
  });

  const { data: webhooks } = useQuery({
    queryKey: ["webhooks"],
    queryFn: () => api.get("/webhooks/").then((r) => r.data),
  });

  const addMut = useMutation({
    mutationFn: (d: { url: string; events: string[] }) =>
      api.post("/webhooks/", { url: d.url, events: d.events }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["webhooks"] }); toast.success("Webhook добавлен"); },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => api.delete(`/webhooks/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["webhooks"] }); toast.success("Webhook удалён"); },
  });

  const { data: billing } = useQuery({
    queryKey: ["billing", "usage"],
    queryFn: () => api.get("/billing/usage").then((r) => r.data),
  });
  const { data: plans } = useQuery({
    queryKey: ["billing", "plans"],
    queryFn: () => api.get("/billing/plans").then((r) => r.data),
  });
  const { data: me } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => api.get("/auth/me").then((r) => r.data),
  });
  const [twoFaCode, setTwoFaCode] = useState("");
  const [twoFaSecret, setTwoFaSecret] = useState("");
  const [twoFaUri, setTwoFaUri] = useState("");
  const setup2faMut = useMutation({
    mutationFn: () => api.post("/auth/2fa/setup").then((r) => r.data),
    onSuccess: (data) => { setTwoFaSecret(data.secret); setTwoFaUri(data.provisioning_uri); },
  });
  const verify2faMut = useMutation({
    mutationFn: (code: string) => api.post("/auth/2fa/verify", { secret: twoFaSecret, code }).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["auth", "me"] }); setTwoFaSecret(""); setTwoFaUri(""); setTwoFaCode(""); },
  });
  const disable2faMut = useMutation({
    mutationFn: (code: string) => api.post("/auth/2fa/disable", { code }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth", "me"] }),
  });

  const testExternalMut = useMutation({
    mutationFn: (d: { source: string; api_key: string; country?: string }) =>
      api.post("/settings/test-external-api", { ...d, country: d.country || "us" }).then((r) => r.data as { ok: boolean; message: string }),
    onSuccess: (data) => toast[data.ok ? "success" : "error"](data.message),
    onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Настройки</h1>
      <div className="space-y-8">
        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Palette size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">White-label</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            Брендинг платформы: название, логотип, цвет. Применяется в сайдбаре.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <input
              value={whitelabel.brand_name ?? ""}
              onChange={(e) => setWhitelabel((p) => ({ ...p, brand_name: e.target.value }))}
              placeholder="Название бренда (например: Dorvey)"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={whitelabel.primary_color ?? ""}
              onChange={(e) => setWhitelabel((p) => ({ ...p, primary_color: e.target.value }))}
              placeholder="Цвет (#10b981)"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={whitelabel.logo_url ?? ""}
              onChange={(e) => setWhitelabel((p) => ({ ...p, logo_url: e.target.value }))}
              placeholder="URL логотипа"
              className="md:col-span-2 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={whitelabel.favicon_url ?? ""}
              onChange={(e) => setWhitelabel((p) => ({ ...p, favicon_url: e.target.value }))}
              placeholder="URL favicon"
              className="md:col-span-2 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
          </div>
          <button
            onClick={() => saveWhitelabelMut.mutate(whitelabel)}
            disabled={saveWhitelabelMut.isPending}
            className="text-sm px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-white disabled:opacity-50"
          >
            {saveWhitelabelMut.isPending ? "Сохранение…" : "Сохранить брендинг"}
          </button>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Bot size={20} className="text-violet-400" />
            <h2 className="text-lg font-medium text-white">OpenAI (AI)</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            API ключ для генерации контента дорвеев, рекомендаций и авто-правок. Без ключа AI-функции отключены.
          </p>
          <p className="text-slate-500 text-xs mb-2">
            Регистрация и ключ: <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">platform.openai.com/api-keys</a>
          </p>
          <div className="flex gap-2 items-start mb-2">
            <input
              value={integrations.openai_api_key ?? ""}
              onChange={(e) => {
                setIntegrations((p) => ({ ...p, openai_api_key: e.target.value }));
                markSensitiveEdited("openai_api_key");
                setOpenaiTestStatus(null);
              }}
              placeholder="sk-..."
              type="password"
              className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <button
              type="button"
              onClick={() => {
                const key = (integrations.openai_api_key ?? "").trim();
                if (!key) {
                  toast.error("Введите API ключ");
                  return;
                }
                setOpenaiTestStatus("checking");
                api.post("/settings/test-openai", { api_key: key })
                  .then((r) => r.data as { ok: boolean; message: string })
                  .then((data) => {
                    setOpenaiTestStatus(data.ok ? "ok" : "error");
                    setOpenaiTestMessage(data.message);
                    toast[data.ok ? "success" : "error"](data.message);
                  })
                  .catch((e: { response?: { data?: { detail?: string } } }) => {
                    setOpenaiTestStatus("error");
                    setOpenaiTestMessage(e?.response?.data?.detail ?? "Ошибка запроса");
                    toast.error(e?.response?.data?.detail ?? "Ошибка запроса");
                  });
              }}
              disabled={openaiTestStatus === "checking" || !(integrations.openai_api_key ?? "").trim()}
              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white text-sm whitespace-nowrap"
            >
              {openaiTestStatus === "checking" ? "Проверка…" : "Проверить"}
            </button>
          </div>
          {openaiTestStatus === "ok" && (
            <p className="flex items-center gap-2 text-emerald-400 text-sm mb-2">
              <CheckCircle size={18} /> Ключ активен, AI доступен
            </p>
          )}
          {openaiTestStatus === "error" && openaiTestMessage && (
            <p className="flex items-center gap-2 text-red-400 text-sm mb-2">
              <span className="text-red-400">✕</span> {openaiTestMessage}
            </p>
          )}
          <p className="text-slate-500 text-xs">Можно также задать OPENAI_API_KEY в .env (глобально для сервера)</p>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Webhook size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Webhooks</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            Выберите события и укажите URL — при наступлении события отправится POST с данными.
          </p>
          <div className="mb-4">
            <p className="text-slate-400 text-xs font-medium mb-2">События для нового webhook</p>
            <div className="flex flex-wrap gap-3">
              {WEBHOOK_EVENT_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={webhookEvents.includes(opt.value)}
                    onChange={() => toggleWebhookEvent(opt.value)}
                    className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700 focus:ring-emerald-500 focus:ring-offset-0 transition-transform group-hover:scale-105"
                  />
                  <span className="text-slate-300 text-sm group-hover:text-white transition-colors">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-4 mb-4">
            <input
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://your-server.com/webhook"
              className="flex-1 px-3 py-2 bg-slate-700/80 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500 transition-all"
            />
            <button
              onClick={() => addMut.mutate({ url: webhookUrl, events: webhookEvents })}
              disabled={!webhookUrl.trim() || addMut.isPending || webhookEvents.length === 0}
              className="btn-lift px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-all duration-200"
            >
              Добавить
            </button>
          </div>
          {webhooks?.length ? (
            <div className="space-y-2">
              {webhooks.map((w: { id: number; url: string; events: string[] }, i: number) => (
                <div key={w.id} className="flex items-center justify-between py-3 px-3 rounded-lg bg-slate-700/40 border border-slate-600/50 hover:border-slate-500 transition-all duration-200 animate-fade-in-up" style={{ animationDelay: `${i * 30}ms` }}>
                  <code className="text-slate-300 text-sm truncate flex-1 mr-3">{w.url}</code>
                  <span className="text-slate-500 text-xs shrink-0 mr-2">{w.events?.length ?? 0} событий</span>
                  <button
                    onClick={() => delMut.mutate(w.id)}
                    className="text-red-400 hover:text-red-300 hover:underline text-sm transition-colors"
                  >
                    Удалить
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">Нет webhooks</p>
          )}
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-amber-400" />
            <h2 className="text-lg font-medium text-white">Аналитика и прибыльность</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            Порог кликов за период: дорвеи с меньшим числом кликов не учитываются в доле «прибыльных» на дашборде.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-slate-300 text-sm">Минимум кликов для учёта в статистике прибыльности</label>
            <input
              type="number"
              min={1}
              max={500}
              value={integrations.min_clicks_for_profit ?? 20}
              onChange={(e) =>
                setIntegrations((p) => ({
                  ...p,
                  min_clicks_for_profit: Math.max(1, Math.min(500, parseInt(e.target.value, 10) || 20)),
                }))
              }
              className="w-24 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 transition-all"
            />
            <span className="text-slate-500 text-sm">(по умолчанию 20)</span>
          </div>
          <p className="text-slate-500 text-xs mt-2">
            Сохраните интеграции внизу страницы, чтобы применить.
          </p>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-violet-400" />
            <h2 className="text-lg font-medium text-white">Внешние данные для аналитики офферов</h2>
          </div>
          <p className="text-slate-400 text-sm mb-2">
            Подключение внешних источников (новости по странам, тренды, сезонность) даёт более точный прогноз прибыльности оффера и рекомендации «какие офферы/страны брать».
          </p>
          <p className="text-slate-500 text-xs mb-3">
            Подход: сначала подключаем большие полные наборы данных, потом дополняем новыми источниками по мере появления.
          </p>
          <label className="flex items-center gap-3 cursor-pointer mb-3">
            <input
              type="checkbox"
              checked={integrations.external_data_enabled ?? false}
              onChange={(e) => setIntegrations((p) => ({ ...p, external_data_enabled: e.target.checked }))}
              className="w-4 h-4 rounded border-slate-600 text-violet-600 bg-slate-700 focus:ring-violet-500"
            />
            <span className="text-slate-300">Использовать внешние данные в аналитике (новости по странам, сезонность)</span>
          </label>
          <div className="grid grid-cols-1 gap-3 mb-3">
            <div>
              <label className="block text-slate-400 text-sm mb-1">NewsAPI.org API Key</label>
              <div className="flex gap-2">
                <input
                  value={integrations.news_api_key ?? ""}
                  onChange={(e) => { setIntegrations((p) => ({ ...p, news_api_key: e.target.value })); markSensitiveEdited("news_api_key"); }}
                  placeholder="Ключ с newsapi.org (новости по странам)"
                  className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                />
                <button
                  type="button"
                  onClick={() => testExternalMut.mutate({ source: "newsapi", api_key: integrations.news_api_key ?? "" })}
                  disabled={!integrations.news_api_key?.trim() || testExternalMut.isPending}
                  className="px-3 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm flex items-center gap-1"
                  title="Проверить подключение"
                >
                  <CheckCircle size={16} />
                  {testExternalMut.isPending ? "…" : "Проверить"}
                </button>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-slate-400 text-sm mb-1">GNews API Key (опц.)</label>
                <p className="text-slate-500 text-xs mb-1">Регистрация: <a href="https://gnews.io/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">gnews.io</a></p>
                <div className="flex gap-2">
                  <input
                    value={integrations.gnews_api_key ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, gnews_api_key: e.target.value })); markSensitiveEdited("gnews_api_key"); }}
                    placeholder="gnews.io"
                    className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                  <button
                    type="button"
                    onClick={() => testExternalMut.mutate({ source: "gnews", api_key: integrations.gnews_api_key ?? "" })}
                    disabled={!integrations.gnews_api_key?.trim() || testExternalMut.isPending}
                    className="px-2 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm"
                    title="Проверить"
                  >
                    <CheckCircle size={16} />
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Mediastack API Key (опц.)</label>
                <p className="text-slate-500 text-xs mb-1">Регистрация: <a href="https://mediastack.com/signup" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">mediastack.com/signup</a></p>
                <div className="flex gap-2">
                  <input
                    value={integrations.mediastack_api_key ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, mediastack_api_key: e.target.value })); markSensitiveEdited("mediastack_api_key"); }}
                    placeholder="mediastack.com"
                    className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                  <button
                    type="button"
                    onClick={() => testExternalMut.mutate({ source: "mediastack", api_key: integrations.mediastack_api_key ?? "" })}
                    disabled={!integrations.mediastack_api_key?.trim() || testExternalMut.isPending}
                    className="px-2 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm"
                    title="Проверить"
                  >
                    <CheckCircle size={16} />
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Guardian API Key (опц.)</label>
                <p className="text-slate-500 text-xs mb-1">Регистрация: <a href="https://open-platform.theguardian.com/access/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">open-platform.theguardian.com/access</a></p>
                <div className="flex gap-2">
                  <input
                    value={integrations.guardian_api_key ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, guardian_api_key: e.target.value })); markSensitiveEdited("guardian_api_key"); }}
                    placeholder="theguardian.com/open-platform"
                    className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                  <button
                    type="button"
                    onClick={() => testExternalMut.mutate({ source: "guardian", api_key: integrations.guardian_api_key ?? "" })}
                    disabled={!integrations.guardian_api_key?.trim() || testExternalMut.isPending}
                    className="px-2 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm"
                    title="Проверить"
                  >
                    <CheckCircle size={16} />
                  </button>
                </div>
              </div>
            </div>
            <p className="text-slate-500 text-xs">Новости: приоритет NewsAPI; при его отсутствии используются GNews, Mediastack, Guardian.</p>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Провайдер подсказки ключей</label>
              <select
                value={integrations.keyword_provider ?? "dataforseo"}
                onChange={(e) => setIntegrations((p) => ({ ...p, keyword_provider: e.target.value || "dataforseo" }))}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
              >
                <option value="dataforseo">DataForSeo — платный, для компаний (логин + пароль API)</option>
                <option value="fetchserp">FetchSERP — 250 бесплатных кредитов, физлица (API ключ)</option>
                <option value="google_ads">Google Ads API — подсказки и объём (Developer Token + OAuth)</option>
              </select>
              <p className="text-slate-500 text-xs mt-1">
                {integrations.keyword_provider === "fetchserp"
                  ? "Подсказки ключей и объём по странам. Бесплатный старт на fetchserp.com, затем кредиты."
                  : integrations.keyword_provider === "google_ads"
                  ? "Официальный API Google: подсказки и объём поиска. Нужен аккаунт Google Ads, Developer Token и OAuth (client_id, client_secret, refresh_token)."
                  : "Большая база ключей по гео. Платный сервис, часто только для юрлиц (app.dataforseo.com)."}
              </p>
            </div>
            {(integrations.keyword_provider ?? "dataforseo") === "dataforseo" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 text-sm mb-1">DataForSeo Login</label>
                  <p className="text-slate-500 text-xs mb-1">Вход/регистрация: <a href="https://app.dataforseo.com/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">app.dataforseo.com</a></p>
                  <input
                    value={integrations.dataforseo_login ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, dataforseo_login: e.target.value })); markSensitiveEdited("dataforseo_login"); }}
                    placeholder="Логин с app.dataforseo.com"
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">DataForSeo Password</label>
                  <input
                    type="password"
                    value={integrations.dataforseo_password ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, dataforseo_password: e.target.value })); markSensitiveEdited("dataforseo_password"); }}
                    placeholder="Пароль API"
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
              </div>
            )}
            {(integrations.keyword_provider ?? "dataforseo") === "fetchserp" && (
              <div>
                <label className="block text-slate-400 text-sm mb-1">FetchSERP API Key</label>
                <p className="text-slate-500 text-xs mb-1">Получить ключ: <a href="https://www.fetchserp.com/app" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">fetchserp.com/app</a>. Документация API: <a href="https://docs.fetchserp.com/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">docs.fetchserp.com</a>. Копируйте ключ целиком из ЛК, без пробелов.</p>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={integrations.fetchserp_api_key ?? ""}
                    onChange={(e) => {
                      setIntegrations((p) => ({ ...p, fetchserp_api_key: e.target.value }));
                      markSensitiveEdited("fetchserp_api_key");
                      setFetchserpTestStatus(null);
                    }}
                    placeholder="Ключ с fetchserp.com/app"
                    className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const key = (integrations.fetchserp_api_key ?? "").trim();
                      if (!key) {
                        toast.error("Введите API ключ");
                        return;
                      }
                      setFetchserpTestStatus("checking");
                      api.post("/settings/test-external-api", { source: "fetchserp", api_key: key })
                        .then((r) => r.data as { ok: boolean; message: string })
                        .then((data) => {
                          setFetchserpTestStatus(data.ok ? "ok" : "error");
                          setFetchserpTestMessage(data.message || "");
                          toast[data.ok ? "success" : "error"](data.message);
                        })
                        .catch((e: { response?: { data?: { detail?: string; message?: string } } }) => {
                          setFetchserpTestStatus("error");
                          const msg = e?.response?.data?.message ?? e?.response?.data?.detail;
                          setFetchserpTestMessage(msg ?? "Ошибка сервера. Попробуйте позже.");
                          toast.error(msg ?? "Ошибка сервера. Попробуйте позже.");
                        });
                    }}
                    disabled={fetchserpTestStatus === "checking" || !(integrations.fetchserp_api_key ?? "").trim()}
                    className="px-4 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm flex items-center gap-1 whitespace-nowrap"
                    title="Проверить ключ и подключение"
                  >
                    <CheckCircle size={16} />
                    {fetchserpTestStatus === "checking" ? "Проверка…" : "Проверить"}
                  </button>
                </div>
                {fetchserpTestStatus === "ok" && (
                  <p className="flex items-center gap-2 text-emerald-400 text-sm mt-2">
                    <CheckCircle size={18} /> Ключ действителен, подключение успешно
                  </p>
                )}
                {fetchserpTestStatus === "error" && fetchserpTestMessage && (
                  <p className="flex items-center gap-2 text-red-400 text-sm mt-2">
                    <span className="text-red-400">✕</span> {fetchserpTestMessage}
                  </p>
                )}
              </div>
            )}
            {(integrations.keyword_provider ?? "dataforseo") === "google_ads" && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 space-y-0">
                <div className="md:col-span-2">
                  <p className="text-slate-500 text-xs mb-2">
                    Документация: <a href="https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Keyword Plan Idea Service</a>. В Google Cloud Console добавь в OAuth-клиента redirect URI: <code className="bg-slate-700 px-1 rounded">https://ваш-бэкенд/api/settings/google-ads-oauth-callback</code>.
                  </p>
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Developer Token</label>
                  <p className="text-slate-500 text-xs mb-1">Где взять: Google Ads (<a href="https://ads.google.com" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">ads.google.com</a>) → Инструменты и настройки (иконка шестерёнки) → Настройки → API Center. Для тестовых аккаунтов нужен режим <strong>Test</strong>; Basic/Standard — после одобрения заявки.</p>
                  <div className="relative flex">
                    <input
                      type={showGoogleAdsDevToken ? "text" : "password"}
                      value={integrations.google_ads_developer_token ?? ""}
                      onChange={(e) => { setIntegrations((p) => ({ ...p, google_ads_developer_token: e.target.value })); markSensitiveEdited("google_ads_developer_token"); }}
                      placeholder="Из Google Ads API Center"
                      className="w-full px-3 py-2 pr-10 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                    />
                    <button type="button" onClick={() => setShowGoogleAdsDevToken((v) => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white" title={showGoogleAdsDevToken ? "Скрыть" : "Показать"}>
                      {showGoogleAdsDevToken ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Client ID (OAuth)</label>
                  <p className="text-slate-500 text-xs mb-1">Где взять: <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Google Cloud Console → APIs &amp; Services → Credentials</a>. Создайте OAuth 2.0 Client (тип Desktop или Web). Client ID — строка вида <code className="bg-slate-700 px-1 rounded">xxx.apps.googleusercontent.com</code>.</p>
                  <input
                    value={integrations.google_ads_client_id ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, google_ads_client_id: e.target.value })); markSensitiveEdited("google_ads_client_id"); }}
                    placeholder="xxx.apps.googleusercontent.com"
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Client Secret (OAuth)</label>
                  <div className="relative flex">
                    <input
                      type={showGoogleAdsSecret ? "text" : "password"}
                      value={integrations.google_ads_client_secret ?? ""}
                      onChange={(e) => { setIntegrations((p) => ({ ...p, google_ads_client_secret: e.target.value })); markSensitiveEdited("google_ads_client_secret"); }}
                      placeholder="GOCSPX-..."
                      className="w-full px-3 py-2 pr-10 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                    />
                    <button type="button" onClick={() => setShowGoogleAdsSecret((v) => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white" title={showGoogleAdsSecret ? "Скрыть" : "Показать"}>
                      {showGoogleAdsSecret ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Refresh Token (OAuth)</label>
                  <p className="text-slate-500 text-xs mb-1">Не скачивается вручную: нажмите «Получить refresh token», войдите в Google — токен сохранится автоматически. Нужны сохранённые Client ID и Client Secret.</p>
                  <div className="flex gap-2">
                    <div className="relative flex flex-1">
                      <input
                        type={showGoogleAdsRefresh ? "text" : "password"}
                        value={integrations.google_ads_refresh_token ?? ""}
                        onChange={(e) => { setIntegrations((p) => ({ ...p, google_ads_refresh_token: e.target.value })); setGoogleAdsTestStatus(null); markSensitiveEdited("google_ads_refresh_token"); }}
                        placeholder="1//..."
                        className="w-full px-3 py-2 pr-10 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                      />
                      <button type="button" onClick={() => setShowGoogleAdsRefresh((v) => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white" title={showGoogleAdsRefresh ? "Скрыть" : "Показать"}>
                        {showGoogleAdsRefresh ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={async () => {
                        const cid = (integrations.google_ads_client_id ?? "").trim();
                        const secret = (integrations.google_ads_client_secret ?? "").trim();
                        if (!cid || !secret) { toast.error("Введите Client ID и Client Secret"); return; }
                        try {
                          const { data } = await api.post<{ url: string; redirect_uri?: string }>("/settings/google-ads-oauth-start", { client_id: cid, client_secret: secret });
                          if (data?.url) {
                            if (data.redirect_uri) setGoogleAdsRedirectUri(data.redirect_uri);
                            googleAdsPopupRef.current = window.open(data.url, "google_ads_oauth", "width=600,height=700");
                          } else toast.error("Не получен URL");
                        } catch (err: unknown) {
                          const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
                          toast.error(msg || "Ошибка запуска OAuth");
                        }
                      }}
                      className="px-4 py-2 bg-slate-600 hover:bg-slate-500 disabled:opacity-50 rounded-lg text-white text-sm whitespace-nowrap"
                    >
                      Получить refresh token
                    </button>
                  </div>
                  {googleAdsRedirectUri && (
                    <p className="text-slate-500 text-xs mt-2 flex flex-wrap items-center gap-2">
                      <span>При ошибке «redirect_uri_mismatch» добавь в Google Cloud Console → Credentials → OAuth-клиент → Authorized redirect URIs этот адрес:</span>
                      <code className="bg-slate-700 px-2 py-1 rounded text-slate-300 break-all">{googleAdsRedirectUri}</code>
                      <button
                        type="button"
                        onClick={() => { navigator.clipboard.writeText(googleAdsRedirectUri); toast.success("Скопировано"); }}
                        className="text-emerald-400 hover:underline text-xs"
                      >
                        Копировать
                      </button>
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Customer ID (необязательно)</label>
                  <p className="text-slate-500 text-xs mb-1">ID рекламного аккаунта (без дефисов или 123-456-7890). Для подсказок ключей используется этот аккаунт; если пусто — берётся первый доступный. <strong>Для тестового токена</strong> укажите ID из «Настройки дочерних аккаунтов» вашего MCC (например 403-443-4560), а не другой аккаунт из переключателя (например 704-609-6309). Тестовый аккаунт можно создать кнопкой ниже (под тестовым MCC).</p>
                  <input
                    type="text"
                    value={integrations.google_ads_customer_id ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, google_ads_customer_id: e.target.value })); markSensitiveEdited("google_ads_customer_id"); }}
                    placeholder="123-456-7890"
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                  <p className="text-slate-500 text-xs mt-1">
                    <strong>Manager account ID (MCC)</strong> — если используете тестовый Developer Token и дочерний аккаунт (как выше), укажите ID тестового MCC, например <code className="bg-slate-700 px-1 rounded">185-780-6498</code>. Без этого подсказки ключей вернут «PERMISSION_DENIED / only test accounts».
                  </p>
                  <label className="block text-slate-400 text-xs mt-2 mb-0.5">Manager account ID (MCC)</label>
                  <input
                    type="text"
                    value={integrations.google_ads_manager_customer_id ?? ""}
                    onChange={(e) => { setIntegrations((p) => ({ ...p, google_ads_manager_customer_id: e.target.value })); markSensitiveEdited("google_ads_manager_customer_id"); }}
                    placeholder="185-780-6498 (MCC)"
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                  <p className="text-slate-500 text-xs mt-1">
                    Тестовый менеджер (MCC) создаётся по ссылке:{" "}
                    <a href="https://ads.google.com/nav/selectaccount?sf=mt" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Создать тестовый MCC</a>.
                    Под ним можно создать тестовый аккаунт программно:
                  </p>
                  <button
                    type="button"
                    disabled={googleAdsCreateTestLoading || saveIntegrationsMut.isPending}
                    onClick={async () => {
                      setGoogleAdsCreateTestLoading(true);
                      try {
                        const { data } = await api.post<{ customer_id: string; customer_id_formatted: string }>(
                          "/settings/google-ads-create-test-account",
                          { manager_customer_id: (integrations.google_ads_manager_customer_id ?? integrations.google_ads_customer_id ?? "").trim() || undefined }
                        );
                        setIntegrations((p) => ({ ...p, google_ads_customer_id: data.customer_id_formatted }));
                        markSensitiveEdited("google_ads_customer_id");
                        toast.success(`Создан тестовый аккаунт: ${data.customer_id_formatted}. Подставлен в Customer ID.`);
                      } catch (e: unknown) {
                        const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Ошибка создания тестового аккаунта";
                        toast.error(typeof msg === "string" ? msg : "Ошибка создания тестового аккаунта");
                      } finally {
                        setGoogleAdsCreateTestLoading(false);
                      }
                    }}
                    className="mt-2 px-3 py-1.5 bg-slate-600 hover:bg-slate-500 disabled:opacity-50 rounded-lg text-white text-sm"
                  >
                    {googleAdsCreateTestLoading ? "Создание…" : "Создать тестовый аккаунт (через API)"}
                  </button>
                </div>
                <div className="md:col-span-2 flex items-center gap-3 flex-wrap">
                  <button
                    type="button"
                    onClick={() => {
                      saveIntegrationsMut.mutate(integrations, {
                        onSuccess: () => {
                          setGoogleAdsTestStatus("checking");
                          api.post("/settings/test-external-api", { source: "google_ads" })
                            .then((r) => r.data as { ok: boolean; message: string })
                            .then((data) => {
                              setGoogleAdsTestStatus(data.ok ? "ok" : "error");
                              setGoogleAdsTestMessage(data.message || "");
                              toast[data.ok ? "success" : "error"](data.message);
                            })
                            .catch((e: { response?: { data?: { detail?: string } } }) => {
                              setGoogleAdsTestStatus("error");
                              const msg = e?.response?.data?.detail ?? "Ошибка сервера";
                              setGoogleAdsTestMessage(msg);
                              toast.error(msg);
                            });
                        },
                        onError: () => toast.error("Сначала сохраните настройки"),
                      });
                    }}
                    disabled={googleAdsTestStatus === "checking" || saveIntegrationsMut.isPending}
                    className="px-4 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm flex items-center gap-1"
                    title="Проверить подключение (refresh token)"
                  >
                    <CheckCircle size={16} />
                    {googleAdsTestStatus === "checking" ? "Проверка…" : "Проверить"}
                  </button>
                  {googleAdsTestStatus === "ok" && (
                    <p className="flex items-center gap-2 text-emerald-400 text-sm">Подключение успешно</p>
                  )}
                  {googleAdsTestStatus === "error" && googleAdsTestMessage && (
                    <p className="flex items-center gap-2 text-red-400 text-sm">{googleAdsTestMessage}</p>
                  )}
                </div>
              </div>
            )}
            <p className="text-slate-500 text-xs">Подсказки ключей по объёму и гео: Ключевые слова → Подтянуть из внешних источников.</p>
            <div>
              <label className="block text-slate-400 text-sm mb-1">URL данных сезонности (опционально)</label>
              <input
                value={integrations.seasonality_data_url ?? ""}
                onChange={(e) => setIntegrations((p) => ({ ...p, seasonality_data_url: e.target.value }))}
                placeholder="https://... JSON с коэффициентами по странам/месяцам"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
            </div>
          </div>
          <div className="rounded-lg bg-slate-800/80 border border-slate-600 p-3 text-sm space-y-2">
            <p className="text-slate-300 font-medium">Какие ещё источники подключать и как:</p>
            <ul className="text-slate-400 list-disc list-inside space-y-1 text-xs">
              <li><strong className="text-slate-300">Рынок по странам</strong> — REST Countries и подобные API; при наличии — отчёты по CPM/трендам (URL или ключ в настройках).</li>
              <li><strong className="text-slate-300">Сезонность</strong> — свой JSON по гео/месяцу или внешний URL (поле выше).</li>
              <li><strong className="text-slate-300">Дополнительно</strong> — полный каталог: <code className="bg-slate-700 px-1 rounded">docs/EXTERNAL_DATA_SOURCES.md</code> в репозитории.</li>
            </ul>
          </div>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Send size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Уведомления</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Telegram и Slack — уведомления о деплое и событиях.</p>
          <p className="text-slate-500 text-xs mb-2">
            Telegram: бот — <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">t.me/BotFather</a>, Chat ID — через <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">@userinfobot</a>. Slack: <a href="https://api.slack.com/messaging/webhooks" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Incoming Webhooks</a>.
          </p>
          <div className="space-y-4 mb-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                value={integrations.telegram_bot_token ?? ""}
                onChange={(e) => { setIntegrations((p) => ({ ...p, telegram_bot_token: e.target.value })); markSensitiveEdited("telegram_bot_token"); }}
                placeholder="Telegram Bot Token"
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
              <input
                value={integrations.telegram_chat_id ?? ""}
                onChange={(e) => { setIntegrations((p) => ({ ...p, telegram_chat_id: e.target.value })); markSensitiveEdited("telegram_chat_id"); }}
                placeholder="Telegram Chat ID"
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
            </div>
            <input
              value={integrations.slack_webhook_url ?? ""}
              onChange={(e) => { setIntegrations((p) => ({ ...p, slack_webhook_url: e.target.value })); markSensitiveEdited("slack_webhook_url"); }}
              placeholder="Slack Incoming Webhook URL (https://hooks.slack.com/...)"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <label className="flex items-center gap-3 cursor-pointer mt-2">
              <input
                type="checkbox"
                checked={integrations.email_notifications_enabled ?? false}
                onChange={(e) => setIntegrations((p) => ({ ...p, email_notifications_enabled: e.target.checked }))}
                className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700"
              />
              <span className="text-slate-300">Email уведомления (на адрес аккаунта, нужен SMTP в .env)</span>
            </label>
          </div>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Search size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Google Search Console</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">OAuth Client ID, Secret и Refresh Token для отправки sitemap.</p>
          <p className="text-slate-500 text-xs mb-2">
            GSC: <a href="https://search.google.com/search-console" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">search.google.com/search-console</a>. OAuth-ключи: <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">Google Cloud Console → Credentials</a>.
          </p>
          <p className="text-slate-500 text-xs mb-2">В Google Console в «Authorized redirect URIs» добавьте: <code className="bg-slate-700 px-1 rounded">{typeof window !== "undefined" ? `${window.location.origin}/api/settings/gsc-oauth-callback` : "https://ваш-домен/api/settings/gsc-oauth-callback"}</code></p>
          <p className="text-slate-500 text-xs mb-4">Для целевой страны в поиске укажите её в GSC → Настройки → International Targeting; регион кампании держите таким же (US, RU и т.д.).</p>
          <div className="space-y-4 mb-4">
            <input
              value={integrations.gsc_client_id ?? ""}
              onChange={(e) => { setIntegrations((p) => ({ ...p, gsc_client_id: e.target.value })); markSensitiveEdited("gsc_client_id"); }}
              placeholder="Client ID"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.gsc_client_secret ?? ""}
              onChange={(e) => { setIntegrations((p) => ({ ...p, gsc_client_secret: e.target.value })); markSensitiveEdited("gsc_client_secret"); }}
              placeholder="Client Secret"
              type="password"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <div className="flex gap-2 items-center">
              <input
                value={integrations.gsc_refresh_token ?? ""}
                onChange={(e) => { setIntegrations((p) => ({ ...p, gsc_refresh_token: e.target.value })); markSensitiveEdited("gsc_refresh_token"); }}
                placeholder="Refresh Token"
                className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
              <button
                type="button"
                onClick={() => {
                  if (!(integrations.gsc_client_id ?? "").trim() || !(integrations.gsc_client_secret ?? "").trim()) {
                    toast.error("Сначала введите Client ID и Client Secret и нажмите «Сохранить интеграции», затем получите Refresh Token.");
                    return;
                  }
                  saveIntegrationsMut.mutate(integrations, {
                    onSuccess: () => {
                      api.get<{ redirect_url: string }>("/settings/gsc-oauth-start")
                        .then((r) => {
                          if (r.data?.redirect_url) window.location.href = r.data.redirect_url;
                          else toast.error("Не удалось получить ссылку авторизации");
                        })
                        .catch((e: { response?: { data?: { detail?: string } } }) => toast.error(e?.response?.data?.detail ?? "Ошибка"));
                    },
                    onError: () => toast.error("Сначала сохраните Client ID и Client Secret"),
                  });
                }}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 rounded-lg text-white text-sm whitespace-nowrap"
              >
                Получить Refresh Token
              </button>
            </div>
          </div>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Search size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Bing Webmaster</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">API ключ для отправки sitemap в Bing.</p>
          <p className="text-slate-500 text-xs mb-2">Регистрация: <a href="https://www.bing.com/webmasters" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">bing.com/webmasters</a>. Ключ: Настройки → Доступ по API → Ключ API.</p>
          <div className="flex gap-2">
            <input
              type="password"
              value={integrations.bing_api_key ?? ""}
              onChange={(e) => {
                setIntegrations((p) => ({ ...p, bing_api_key: e.target.value }));
                markSensitiveEdited("bing_api_key");
                setBingTestStatus(null);
              }}
              placeholder="API Key"
              className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <button
              type="button"
              onClick={() => {
                const key = (integrations.bing_api_key ?? "").trim();
                if (!key) {
                  toast.error("Введите API ключ");
                  return;
                }
                setBingTestStatus("checking");
                api.post("/settings/test-external-api", { source: "bing", api_key: key })
                  .then((r) => r.data as { ok: boolean; message: string })
                  .then((data) => {
                    setBingTestStatus(data.ok ? "ok" : "error");
                    setBingTestMessage(data.message || "");
                    toast[data.ok ? "success" : "error"](data.message);
                  })
                  .catch((e: { response?: { data?: { detail?: string; message?: string } } }) => {
                    setBingTestStatus("error");
                    const msg = e?.response?.data?.message ?? e?.response?.data?.detail;
                    setBingTestMessage(msg ?? "Ошибка сервера. Попробуйте позже.");
                    toast.error(msg ?? "Ошибка сервера. Попробуйте позже.");
                  });
              }}
              disabled={bingTestStatus === "checking" || !(integrations.bing_api_key ?? "").trim()}
              className="px-4 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm flex items-center gap-1 whitespace-nowrap"
              title="Проверить ключ и связь с Bing"
            >
              <CheckCircle size={16} />
              {bingTestStatus === "checking" ? "Проверка…" : "Проверить"}
            </button>
          </div>
          {bingTestStatus === "ok" && (
            <p className="flex items-center gap-2 text-emerald-400 text-sm mt-2">
              <CheckCircle size={18} /> Ключ действителен, связь с Bing установлена
            </p>
          )}
          {bingTestStatus === "error" && bingTestMessage && (
            <p className="flex items-center gap-2 text-red-400 text-sm mt-2">
              <span className="text-red-400">✕</span> {bingTestMessage}
            </p>
          )}
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Shield size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">SSL</h2>
          </div>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={integrations.ssl_auto_enabled ?? false}
              onChange={(e) => setIntegrations((p) => ({ ...p, ssl_auto_enabled: e.target.checked }))}
              className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700 focus:ring-emerald-500"
            />
            <span className="text-slate-300">Автоматически выпускать SSL (Let's Encrypt) при деплое</span>
          </label>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Voluum / Binom</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">API для трекинга конверсий.</p>
          <p className="text-slate-500 text-xs mb-2">Voluum: <a href="https://voluum.com/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">voluum.com</a> (API в кабинете). Binom: <a href="https://binom.org/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">binom.org</a> (API в настройках).</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <input
              value={integrations.voluum_api_key ?? ""}
              onChange={(e) => { setIntegrations((p) => ({ ...p, voluum_api_key: e.target.value })); markSensitiveEdited("voluum_api_key"); }}
              placeholder="Voluum API Key"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.voluum_api_url ?? ""}
              onChange={(e) => { setIntegrations((p) => ({ ...p, voluum_api_url: e.target.value })); markSensitiveEdited("voluum_api_url"); }}
              placeholder="Voluum API URL"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.binom_api_key ?? ""}
              onChange={(e) => { setIntegrations((p) => ({ ...p, binom_api_key: e.target.value })); markSensitiveEdited("binom_api_key"); }}
              placeholder="Binom API Key"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.binom_api_url ?? ""}
              onChange={(e) => { setIntegrations((p) => ({ ...p, binom_api_url: e.target.value })); markSensitiveEdited("binom_api_url"); }}
              placeholder="Binom API URL"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
          </div>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <MousePointer size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Heatmaps</h2>
          </div>
          <p className="text-slate-400 text-sm mb-2">
            Укажите только ID — код скриптов вставляется в страницы дорвеев автоматически при деплое, писать ничего вручную не нужно.
          </p>
          <p className="text-slate-500 text-xs mb-4">
            Hotjar: тепловые карты, записи сессий, опросы. Clarity (Microsoft): записи сессий, клики, прокрутка — бесплатно.
          </p>
          <p className="text-slate-500 text-xs mb-2">Hotjar: <a href="https://www.hotjar.com/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">hotjar.com</a>. Clarity: <a href="https://clarity.microsoft.com/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">clarity.microsoft.com</a>.</p>
          <div className="space-y-3 mb-2">
            <div className="flex gap-2 items-start">
              <input
                value={integrations.hotjar_site_id ?? ""}
                onChange={(e) => {
                  setIntegrations((p) => ({ ...p, hotjar_site_id: e.target.value }));
                  markSensitiveEdited("hotjar_site_id");
                  setHotjarTestStatus(null);
                }}
                placeholder="Hotjar или Contentsquare ID (число или 785bcc77e264f)"
                className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
              <button
                type="button"
                onClick={() => {
                  const id = (integrations.hotjar_site_id ?? "").trim();
                  if (!id) { toast.error("Введите Hotjar Site ID"); return; }
                  setHotjarTestStatus("checking");
                  api.post("/settings/test-external-api", { source: "hotjar", api_key: id })
                    .then((r) => r.data as { ok: boolean; message: string })
                    .then((data) => {
                      setHotjarTestStatus(data.ok ? "ok" : "error");
                      setHotjarTestMessage(data.message || "");
                      toast[data.ok ? "success" : "error"](data.message);
                    })
                    .catch(() => {
                      setHotjarTestStatus("error");
                      setHotjarTestMessage("Ошибка проверки");
                      toast.error("Ошибка проверки");
                    });
                }}
                disabled={hotjarTestStatus === "checking" || !(integrations.hotjar_site_id ?? "").trim()}
                className="px-4 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm flex items-center gap-1 whitespace-nowrap shrink-0"
                title="Проверить ID"
              >
                <CheckCircle size={16} />
                {hotjarTestStatus === "checking" ? "…" : "Проверить"}
              </button>
            </div>
            {hotjarTestStatus === "ok" && <p className="text-emerald-400 text-sm flex items-center gap-2"><CheckCircle size={16} /> {hotjarTestMessage}</p>}
            {hotjarTestStatus === "error" && hotjarTestMessage && <p className="text-red-400 text-sm">✕ {hotjarTestMessage}</p>}
            <div className="flex gap-2 items-start">
              <input
                value={integrations.clarity_project_id ?? ""}
                onChange={(e) => {
                  setIntegrations((p) => ({ ...p, clarity_project_id: e.target.value }));
                  markSensitiveEdited("clarity_project_id");
                  setClarityTestStatus(null);
                }}
                placeholder="Microsoft Clarity Project ID"
                className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
              <button
                type="button"
                onClick={() => {
                  const id = (integrations.clarity_project_id ?? "").trim();
                  if (!id) { toast.error("Введите Clarity Project ID"); return; }
                  setClarityTestStatus("checking");
                  api.post("/settings/test-external-api", { source: "clarity", api_key: id })
                    .then((r) => r.data as { ok: boolean; message: string })
                    .then((data) => {
                      setClarityTestStatus(data.ok ? "ok" : "error");
                      setClarityTestMessage(data.message || "");
                      toast[data.ok ? "success" : "error"](data.message);
                    })
                    .catch(() => {
                      setClarityTestStatus("error");
                      setClarityTestMessage("Ошибка проверки");
                      toast.error("Ошибка проверки");
                    });
                }}
                disabled={clarityTestStatus === "checking" || !(integrations.clarity_project_id ?? "").trim()}
                className="px-4 py-2 bg-emerald-600/80 hover:bg-emerald-600 disabled:opacity-50 rounded-lg text-white text-sm flex items-center gap-1 whitespace-nowrap shrink-0"
                title="Проверить ID"
              >
                <CheckCircle size={16} />
                {clarityTestStatus === "checking" ? "…" : "Проверить"}
              </button>
            </div>
            {clarityTestStatus === "ok" && <p className="text-emerald-400 text-sm flex items-center gap-2"><CheckCircle size={16} /> {clarityTestMessage}</p>}
            {clarityTestStatus === "error" && clarityTestMessage && <p className="text-red-400 text-sm">✕ {clarityTestMessage}</p>}
          </div>
          <p className="text-slate-500 text-xs">Скрипты подставляются в страницы дорвеев автоматически при деплое.</p>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <MousePointer size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Конверсия</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Exit-intent попап при уходе и trust-элементы на дорвеях.</p>
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.exit_intent_enabled ?? false}
                onChange={(e) => setIntegrations((p) => ({ ...p, exit_intent_enabled: e.target.checked }))}
                className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700 focus:ring-emerald-500"
              />
              <span className="text-slate-300">Exit-intent: показывать попап при уходе курсора</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.trust_elements_enabled ?? false}
                onChange={(e) => setIntegrations((p) => ({ ...p, trust_elements_enabled: e.target.checked }))}
                className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700 focus:ring-emerald-500"
              />
              <span className="text-slate-300">Trust-элементы: иконки надёжности (Безопасно, Проверено)</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.click_tracking_enabled ?? false}
                onChange={(e) => setIntegrations((p) => ({ ...p, click_tracking_enabled: e.target.checked }))}
                className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700 focus:ring-emerald-500"
              />
              <span className="text-slate-300">Клик-трекинг: CTA ведёт через /api/analytics/click, считаем клики</span>
            </label>
            <div>
              <label className="block text-slate-400 text-sm mb-1">API Base URL (для клик-трекинга)</label>
              <input
                value={integrations.api_base_url ?? ""}
                onChange={(e) => setIntegrations((p) => ({ ...p, api_base_url: e.target.value }))}
                placeholder="https://your-api.example.com"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
              <p className="text-slate-500 text-xs mt-1">URL вашего Dorvey API. Если пусто — CTA ведёт напрямую на оффер.</p>
            </div>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.visitor_capture_enabled ?? false}
                onChange={(e) => setIntegrations((p) => ({ ...p, visitor_capture_enabled: e.target.checked }))}
                className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700 focus:ring-emerald-500"
              />
              <span className="text-slate-300">Захват посетителей: база по визитам/кликам для remarketing и push</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={integrations.email_capture_enabled ?? false}
                onChange={(e) => setIntegrations((p) => ({ ...p, email_capture_enabled: e.target.checked }))}
                className="w-4 h-4 rounded border-slate-600 text-emerald-600 bg-slate-700 focus:ring-emerald-500"
              />
              <span className="text-slate-300">Сбор email: форма на дорвеях для рассылок</span>
            </label>
            <div className="mt-3 pt-3 border-t border-slate-600">
              <p className="text-slate-400 text-sm mb-2">VAPID ключи для Web Push (кнопка «Подписаться» на дорвеях)</p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => api.post("/settings/vapid/generate").then(() => { toast.success("Ключи сгенерированы"); window.location.reload(); }).catch((e) => toast.error(e?.response?.data?.detail ?? "Ошибка"))}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-sm"
                >
                  Сгенерировать VAPID
                </button>
                {integrations.vapid_public_key && (
                  <span className="text-emerald-400 text-sm">✓ Ключи настроены</span>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Ретаргетинг (Facebook / Google)</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Пиксели для создания аудиторий и ретаргетинга.</p>
          <p className="text-slate-500 text-xs mb-2">Facebook Pixel: <a href="https://business.facebook.com/events_manager" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">business.facebook.com → Events Manager</a>. Google Ads: <a href="https://ads.google.com/" target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:underline">ads.google.com</a> → Инструменты → Конверсии.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-slate-400 text-sm mb-1">Facebook Pixel ID</label>
              <input
                value={integrations.facebook_pixel_id ?? ""}
                onChange={(e) => { setIntegrations((p) => ({ ...p, facebook_pixel_id: e.target.value })); markSensitiveEdited("facebook_pixel_id"); }}
                placeholder="123456789012345"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Google Ads ID</label>
              <input
                value={integrations.google_ads_id ?? ""}
                onChange={(e) => { setIntegrations((p) => ({ ...p, google_ads_id: e.target.value })); markSensitiveEdited("google_ads_id"); }}
                placeholder="AW-123456789"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={() => saveIntegrationsMut.mutate(integrations)}
            disabled={saveIntegrationsMut.isPending}
            className="btn-lift px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl font-medium transition-all"
          >
            {saveIntegrationsMut.isPending ? "Сохранение…" : "Сохранить интеграции"}
          </button>
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <CreditCard size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Billing</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Использование и лимиты тарифного плана.</p>
          {billing ? (
            <div className="space-y-2 text-sm">
              <p className="text-slate-300">План: <span className="text-emerald-400">{billing.plan}</span></p>
              <div className="grid grid-cols-3 gap-4">
                {["doorways", "campaigns", "domains"].map((k) => (
                  <div key={k} className="p-3 bg-slate-700/50 rounded-lg">
                    <p className="text-slate-400">{k}</p>
                    <p className="text-white">{billing.usage?.[k] ?? 0} / {billing.limits?.[k] ?? "—"}</p>
                    {billing.over_limit?.[k] && <p className="text-amber-400 text-xs">Лимит превышен</p>}
                  </div>
                ))}
              </div>
              {plans && Array.isArray(plans) && (
                <p className="text-slate-500 text-xs mt-2">Тарифы: {plans.map((p: [string, { price?: number }]) => `${p[0]} (${p[1]?.price ?? 0} ₽)`).join(", ")}</p>
              )}
            </div>
          ) : (
            <p className="text-slate-500">Загрузка...</p>
          )}
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <Smartphone size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">2FA (двухфакторная аутентификация)</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Дополнительная защита аккаунта через приложение (Google Authenticator, Authy и т.п.).</p>
          {me?.has_2fa ? (
            <div className="space-y-3">
              <p className="text-emerald-400 text-sm">2FA включена</p>
              <div className="flex gap-2 items-center">
                <input value={twoFaCode} onChange={(e) => setTwoFaCode(e.target.value)} placeholder="Код из приложения" className="w-40 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                <button onClick={() => disable2faMut.mutate(twoFaCode)} disabled={!twoFaCode || disable2faMut.isPending} className="px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-sm">Отключить 2FA</button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-slate-400 text-sm">2FA не настроена</p>
              {twoFaUri ? (
                <div className="space-y-2">
                  <p className="text-slate-400 text-sm">Отсканируйте QR в приложении и введите код:</p>
                  <input value={twoFaCode} onChange={(e) => setTwoFaCode(e.target.value)} placeholder="Код" className="w-40 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white" />
                  <button onClick={() => verify2faMut.mutate(twoFaCode)} disabled={!twoFaCode || verify2faMut.isPending} className="ml-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm">Подтвердить</button>
                  <button onClick={() => { setTwoFaSecret(""); setTwoFaUri(""); }} className="ml-2 text-slate-400 hover:text-white text-sm">Отмена</button>
                </div>
              ) : (
                <button onClick={() => setup2faMut.mutate()} disabled={setup2faMut.isPending} className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm">Включить 2FA</button>
              )}
            </div>
          )}
        </div>

        <div className="card-volumetric">
          <div className="flex items-center gap-2 mb-4">
            <SettingsIcon size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Cron</h2>
          </div>
          <p className="text-slate-400 text-sm mb-2">
            Вызывайте раз в день (через cron или внешний планировщик). Либо один вызов <code className="text-emerald-400">POST /api/cron/run-all</code> — выполнит все задачи ниже, включая ранний стоп.
          </p>
          <div className="space-y-2 mb-2">
            <code className="block p-3 bg-slate-900 rounded text-emerald-400 text-sm">
              POST /api/cron/early-pause-24h?min_clicks=50
            </code>
            <span className="text-slate-500 text-xs">Ранний стоп за 24 ч: пауза при 0 конверсий и ≥50 кликов за сутки</span>
          </div>
          <div className="space-y-2 mb-2">
            <code className="block p-3 bg-slate-900 rounded text-emerald-400 text-sm">
              POST /api/cron/early-pause-no-conversions?min_days=2&min_clicks=30
            </code>
            <span className="text-slate-500 text-xs">Ранний стоп: пауза дорвеев за 2–3 дня с трафиком, но 0 конверсий (прибыль на 2–3 день)</span>
          </div>
          <div className="space-y-2 mb-2">
            <code className="block p-3 bg-slate-900 rounded text-emerald-400 text-sm">
              POST /api/cron/auto-rollback?threshold_percent=15&min_days=7
            </code>
            <span className="text-slate-500 text-xs">Авто-откат контента при падении CR</span>
          </div>
          <div className="space-y-2 mb-2">
            <code className="block p-3 bg-slate-900 rounded text-emerald-400 text-sm">
              POST /api/cron/auto-pause-unprofitable?min_days=14
            </code>
            <span className="text-slate-500 text-xs">Пауза убыточных дорвеев</span>
          </div>
          <div className="space-y-2 mb-2">
            <code className="block p-3 bg-slate-900 rounded text-emerald-400 text-sm">
              POST /api/cron/auto-switch-offers?threshold_percent=15&min_days=7
            </code>
            <span className="text-slate-500 text-xs">Автосмена офферов при падении CR (кампании с 2+ офферами)</span>
          </div>
          <div className="space-y-2">
            <code className="block p-3 bg-slate-900 rounded text-emerald-400 text-sm">
              POST /api/cron/pause-on-affiliate-issues?min_days=7
            </code>
            <span className="text-slate-500 text-xs">Пауза при проблемах партнёрки (падение конверсий)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
