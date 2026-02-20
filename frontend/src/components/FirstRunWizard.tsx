import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "../api/client";
import { Button } from "./ui/button";

const WIZARD_DISMISSED_KEY = "dorvey_wizard_done";

export default function FirstRunWizard() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [inProgress, setInProgress] = useState(false);
  const [dismissed, setDismissed] = useState(() => typeof window !== "undefined" && !!localStorage.getItem(WIZARD_DISMISSED_KEY));
  const [form, setForm] = useState({ name: "", affiliate_url: "" });

  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (d: { name: string; affiliate_url: string }) =>
      api.post("/campaigns/", { ...d, language: "ru", locale: "ru-RU", region: "RU", currency: "RUB", status: "active" }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      toast.success("Кампания создана");
      setInProgress(true);
      setStep(2);
    },
    onError: () => toast.error("Ошибка создания кампании"),
  });

  const hasNoCampaigns = !isLoading && Array.isArray(campaigns) && campaigns.length === 0;
  const showWizard = !dismissed && (hasNoCampaigns || inProgress);

  const handleDone = () => {
    localStorage.setItem(WIZARD_DISMISSED_KEY, "1");
    setDismissed(true);
    navigate("/doorways");
  };

  if (!showWizard) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-800 rounded-2xl border border-slate-600 shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 mb-2">
          {[1, 2, 3, 4].map((s) => (
            <span key={s} className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= s ? "bg-emerald-600 text-white" : "bg-slate-700 text-slate-500"}`}>
              {s}
            </span>
          ))}
        </div>
        <h2 className="text-xl font-semibold text-white mb-4">
          {step === 1 && "Первая кампания"}
          {step === 2 && "Домен (опционально)"}
          {step === 3 && "Ключевые слова (опционально)"}
          {step === 4 && "Готово"}
        </h2>

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-slate-400 text-sm">Создайте кампанию — к ней будут привязаны дорвеи и офферы.</p>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Название</label>
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Моя кампания" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500" />
            </div>
            <div>
              <label className="block text-slate-400 text-sm mb-1">Affiliate URL</label>
              <input value={form.affiliate_url} onChange={(e) => setForm((f) => ({ ...f, affiliate_url: e.target.value }))} placeholder="https://..." className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500" />
            </div>
            <div className="flex gap-2 justify-end">
              <Button onClick={() => { setDismissed(true); localStorage.setItem(WIZARD_DISMISSED_KEY, "1"); }} variant="ghost">Позже</Button>
              <Button onClick={() => createMut.mutate(form)} disabled={!form.name.trim() || createMut.isPending}>
                {createMut.isPending ? "Создание…" : "Создать"}
              </Button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <p className="text-slate-400 text-sm">Домен нужен для деплоя дорвеев. Можно добавить в разделе Домены.</p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(3)}>Пропустить</Button>
              <Button onClick={() => { setStep(3); navigate("/domains"); setDismissed(true); localStorage.setItem(WIZARD_DISMISSED_KEY, "1"); }}>Добавить домен</Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-4">
            <p className="text-slate-400 text-sm">Ключевые слова используются для AI-генерации дорвеев.</p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(4)}>Пропустить</Button>
              <Button onClick={() => { setStep(4); navigate("/keywords"); setDismissed(true); localStorage.setItem(WIZARD_DISMISSED_KEY, "1"); }}>Добавить ключи</Button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-4">
            <p className="text-slate-400 text-sm">Можно создавать дорвеи: Дорвеи → Сгенерировать.</p>
            <Button onClick={handleDone} className="w-full">Перейти к дорвеям</Button>
          </div>
        )}
      </div>
    </div>
  );
}
