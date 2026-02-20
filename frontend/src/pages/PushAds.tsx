import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Bell, Send, Eye } from "lucide-react";

export default function PushAds() {
  const [form, setForm] = useState({
    campaign_id: 0,
    doorway_id: 0 as number | undefined,
    title: "",
    body: "",
    url: "",
  });

  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: doorways } = useQuery({
    queryKey: ["doorways", form.campaign_id],
    queryFn: () =>
      api.get("/doorways/", { params: form.campaign_id ? { campaign_id: form.campaign_id } : {} }).then((r) => r.data),
  });

  const sendPushMut = useMutation({
    mutationFn: (d: { campaign_id?: number; doorway_id?: number; title: string; body: string; url?: string }) =>
      api.post("/analytics/send-push", { ...d, campaign_id: d.campaign_id || undefined, doorway_id: d.doorway_id || undefined }).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`Отправлено: ${data.sent} из ${data.total}`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });

  const handleSend = () => {
    if (!form.title.trim()) {
      toast.error("Введите заголовок");
      return;
    }
    if (!form.campaign_id && !form.doorway_id) {
      toast.error("Выберите кампанию или дорвей");
      return;
    }
    sendPushMut.mutate({
      campaign_id: form.campaign_id || undefined,
      doorway_id: form.doorway_id || undefined,
      title: form.title,
      body: form.body,
      url: form.url || undefined,
    });
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
        <Bell className="text-emerald-400" size={28} />
        Конструктор Push-рекламы
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Форма */}
        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-medium text-white mb-4">Создать push-рассылку</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-slate-400 text-sm mb-1">Кампания</label>
              <select
                value={form.campaign_id}
                onChange={(e) => setForm((f) => ({ ...f, campaign_id: +e.target.value, doorway_id: undefined }))}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
              >
                <option value={0}>— Выберите кампанию</option>
                {campaigns?.map((c: { id: number; name: string }) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            {form.campaign_id > 0 && (
              <div>
                <label className="block text-slate-400 text-sm mb-1">Дорвей (опционально)</label>
                <select
                  value={form.doorway_id ?? 0}
                  onChange={(e) => setForm((f) => ({ ...f, doorway_id: +e.target.value || undefined }))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                >
                  <option value={0}>Вся кампания</option>
                  {doorways?.map((d: { id: number; path: string }) => (
                    <option key={d.id} value={d.id}>#{d.id} {d.path}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="block text-slate-400 text-sm mb-1">Заголовок *</label>
              <Input
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="Специальное предложение!"
                className="bg-slate-700 border-slate-600"
                maxLength={65}
              />
              <p className="text-slate-500 text-xs mt-0.5">{form.title.length}/65</p>
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Текст сообщения</label>
              <textarea
                value={form.body}
                onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
                placeholder="Оформите заявку со скидкой до 30%"
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white resize-none"
                rows={3}
                maxLength={120}
              />
              <p className="text-slate-500 text-xs mt-0.5">{form.body.length}/120</p>
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Ссылка при клике</label>
              <Input
                value={form.url}
                onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                placeholder="/ или https://..."
                className="bg-slate-700 border-slate-600"
              />
            </div>
            <Button
              onClick={handleSend}
              disabled={sendPushMut.isPending || !form.title.trim()}
              className="w-full py-6 text-lg"
            >
              <Send size={20} className="mr-2" />
              {sendPushMut.isPending ? "Отправка…" : "Отправить push"}
            </Button>
          </div>
        </div>

        {/* Превью */}
        <div className="bg-slate-800/80 rounded-xl p-6 border border-slate-700">
          <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
            <Eye size={20} className="text-emerald-400" />
            Превью уведомления
          </h2>
          <div className="bg-slate-900 rounded-xl p-4 border border-slate-600">
            <p className="text-slate-400 text-xs mb-3">Как будет выглядеть на устройстве:</p>
            <div className="bg-white rounded-lg shadow-lg p-4 max-w-[320px] text-left">
              <div className="flex gap-3">
                <div className="w-10 h-10 rounded-lg bg-slate-200 flex-shrink-0 flex items-center justify-center">
                  <Bell size={20} className="text-slate-500" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-slate-900 text-sm truncate">
                    {form.title || "Заголовок уведомления"}
                  </p>
                  <p className="text-slate-600 text-xs mt-0.5 line-clamp-2">
                    {form.body || "Текст сообщения"}
                  </p>
                </div>
              </div>
            </div>
          </div>
          <p className="text-slate-500 text-sm mt-4">
            Push приходит всем, кто подписался на уведомления на дорвеях выбранной кампании.
          </p>
        </div>
      </div>
    </div>
  );
}
