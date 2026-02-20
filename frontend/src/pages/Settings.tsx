import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "../api/client";
import { Webhook, Settings as SettingsIcon, Send, Search, Shield, BarChart3, MousePointer, Palette, Bot, CreditCard, Smartphone } from "lucide-react";

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
};

export default function Settings() {
  const qc = useQueryClient();
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookEvents] = useState<string[]>(["doorway.deployed", "doorway.conversion"]);

  const [integrations, setIntegrations] = useState<IntegrationsData>({});
  const [whitelabel, setWhitelabel] = useState<{
    brand_name?: string;
    logo_url?: string;
    primary_color?: string;
    favicon_url?: string;
  }>({});
  const { data: integrationsData } = useQuery({
    queryKey: ["settings", "integrations"],
    queryFn: () => api.get<IntegrationsData>("/settings/integrations/all").then((r) => r.data),
  });
  const { data: whitelabelData } = useQuery({
    queryKey: ["settings", "whitelabel"],
    queryFn: () => api.get("/settings/whitelabel").then((r) => r.data),
  });
  useEffect(() => {
    if (integrationsData) setIntegrations(integrationsData);
  }, [integrationsData]);
  useEffect(() => {
    if (whitelabelData) setWhitelabel(whitelabelData);
  }, [whitelabelData]);

  const saveIntegrationsMut = useMutation({
    mutationFn: (d: IntegrationsData) =>
      api.put("/settings/integrations/all", d).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["settings", "integrations"] }); toast.success("Интеграции сохранены"); },
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

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Настройки</h1>
      <div className="space-y-8">
        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
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

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <Bot size={20} className="text-violet-400" />
            <h2 className="text-lg font-medium text-white">OpenAI (AI)</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            API ключ для генерации контента дорвеев, рекомендаций и авто-правок. Без ключа AI-функции отключены.
          </p>
          <input
            value={integrations.openai_api_key ?? ""}
            onChange={(e) => setIntegrations((p) => ({ ...p, openai_api_key: e.target.value }))}
            placeholder="sk-..."
            type="password"
            className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 mb-2"
          />
          <p className="text-slate-500 text-xs">Можно также задать OPENAI_API_KEY в .env (глобально для сервера)</p>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <Webhook size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Webhooks</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">
            Отправляем POST с данными при событиях: doorway.deployed, doorway.conversion, doorway.rollback, doorway.anomaly (алерт при падении CR).
          </p>
          <div className="flex gap-4 mb-4">
            <input
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://your-server.com/webhook"
              className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <button
              onClick={() => addMut.mutate({ url: webhookUrl, events: webhookEvents })}
              disabled={!webhookUrl.trim() || addMut.isPending}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm"
            >
              Добавить
            </button>
          </div>
          {webhooks?.length ? (
            <div className="space-y-2">
              {webhooks.map((w: { id: number; url: string; events: string[] }) => (
                <div key={w.id} className="flex items-center justify-between py-2 border-b border-slate-700">
                  <code className="text-slate-300 text-sm">{w.url}</code>
                  <button
                    onClick={() => delMut.mutate(w.id)}
                    className="text-red-400 hover:underline text-sm"
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

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <Send size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Уведомления</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Telegram и Slack — уведомления о деплое и событиях.</p>
          <div className="space-y-4 mb-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <input
                value={integrations.telegram_bot_token ?? ""}
                onChange={(e) => setIntegrations((p) => ({ ...p, telegram_bot_token: e.target.value }))}
                placeholder="Telegram Bot Token"
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
              <input
                value={integrations.telegram_chat_id ?? ""}
                onChange={(e) => setIntegrations((p) => ({ ...p, telegram_chat_id: e.target.value }))}
                placeholder="Telegram Chat ID"
                className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
            </div>
            <input
              value={integrations.slack_webhook_url ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, slack_webhook_url: e.target.value }))}
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

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <Search size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Google Search Console</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">OAuth Client ID, Secret и Refresh Token для отправки sitemap.</p>
          <div className="space-y-4 mb-4">
            <input
              value={integrations.gsc_client_id ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, gsc_client_id: e.target.value }))}
              placeholder="Client ID"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.gsc_client_secret ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, gsc_client_secret: e.target.value }))}
              placeholder="Client Secret"
              type="password"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.gsc_refresh_token ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, gsc_refresh_token: e.target.value }))}
              placeholder="Refresh Token"
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
          </div>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <Search size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Bing Webmaster</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">API ключ для отправки sitemap в Bing.</p>
          <input
            value={integrations.bing_api_key ?? ""}
            onChange={(e) => setIntegrations((p) => ({ ...p, bing_api_key: e.target.value }))}
            placeholder="API Key"
            className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 mb-4"
          />
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
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

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Voluum / Binom</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">API для трекинга конверсий.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <input
              value={integrations.voluum_api_key ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, voluum_api_key: e.target.value }))}
              placeholder="Voluum API Key"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.voluum_api_url ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, voluum_api_url: e.target.value }))}
              placeholder="Voluum API URL"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.binom_api_key ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, binom_api_key: e.target.value }))}
              placeholder="Binom API Key"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.binom_api_url ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, binom_api_url: e.target.value }))}
              placeholder="Binom API URL"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
          </div>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <MousePointer size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Heatmaps</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Hotjar и Clarity — для вставки скриптов в шаблоны дорвеев.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <input
              value={integrations.hotjar_site_id ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, hotjar_site_id: e.target.value }))}
              placeholder="Hotjar Site ID"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
            <input
              value={integrations.clarity_project_id ?? ""}
              onChange={(e) => setIntegrations((p) => ({ ...p, clarity_project_id: e.target.value }))}
              placeholder="Microsoft Clarity Project ID"
              className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
            />
          </div>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
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

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Ретаргетинг (Facebook / Google)</h2>
          </div>
          <p className="text-slate-400 text-sm mb-4">Пиксели для создания аудиторий и ретаргетинга.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-slate-400 text-sm mb-1">Facebook Pixel ID</label>
              <input
                value={integrations.facebook_pixel_id ?? ""}
                onChange={(e) => setIntegrations((p) => ({ ...p, facebook_pixel_id: e.target.value }))}
                placeholder="123456789012345"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
              />
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Google Ads ID</label>
              <input
                value={integrations.google_ads_id ?? ""}
                onChange={(e) => setIntegrations((p) => ({ ...p, google_ads_id: e.target.value }))}
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
            className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg font-medium"
          >
            {saveIntegrationsMut.isPending ? "Сохранение…" : "Сохранить интеграции"}
          </button>
        </div>

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
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

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
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

        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <div className="flex items-center gap-2 mb-4">
            <SettingsIcon size={20} className="text-emerald-400" />
            <h2 className="text-lg font-medium text-white">Cron</h2>
          </div>
          <p className="text-slate-400 text-sm mb-2">
            Вызывайте раз в день (через cron или внешний планировщик):
          </p>
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
