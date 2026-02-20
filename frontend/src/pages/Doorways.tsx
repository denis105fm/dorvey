import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { EmptyState } from "../components/ui/empty-state";
import { Skeleton } from "../components/ui/skeleton";
import { DropdownMenu, DropdownMenuItem } from "../components/ui/dropdown-menu";
import { FileText, MoreVertical, ExternalLink, ChevronRight, ChevronLeft, Search, Layers, Plus, Check, TrendingUp, TrendingDown, Minus } from "lucide-react";

type Rec = { type: string; text: string };
type ContentVariant = { title?: string; content?: string; meta_description?: string };
type Doorway = { id: number; campaign_id: number; domain_id: number; path: string; title?: string; status: string; content_variants?: ContentVariant[]; pause_reason?: string | null };
type DoorwayMetric = {
  doorway_id: number; clicks: number; revenue: number; conversions: number;
  profit_status: string; health_score: number; profit_probability?: string;
  benchmark_cr?: number | null; benchmark_roi?: number | null;
  above_benchmark_cr?: boolean | null; above_benchmark_roi?: boolean | null;
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  deployed: "Задеплоен",
  indexed: "Проиндексирован",
  optimizing: "Оптимизация",
  paused: "На паузе",
};

const PER_PAGE = 10;

export default function Doorways() {
  const qc = useQueryClient();
  const [wizardStep, setWizardStep] = useState(0);
  const [showGenerate, setShowGenerate] = useState(false);
  const [deployDoorwayId, setDeployDoorwayId] = useState<number | null>(null);
  const [gen, setGen] = useState({ campaign_id: 1, domain_id: 1, keyword: "", path: "/", save: true, generate_faq: false });
  const [batchKeywords, setBatchKeywords] = useState("");
  const [result, setResult] = useState<{ html?: string; doorway_id?: number; validation_violations?: string[] } | null>(null);
  const [recsDoorwayId, setRecsDoorwayId] = useState<number | null>(null);
  const [panelDoorwayId, setPanelDoorwayId] = useState<number | null>(null);
  const [panelType, setPanelType] = useState<"quality" | "predict" | "broken" | null>(null);
  const [variantsDoorwayId, setVariantsDoorwayId] = useState<number | null>(null);
  const [filterCampaign, setFilterCampaign] = useState<string>("");
  const [filterDomain, setFilterDomain] = useState<string>("");
  const [filterProfit, setFilterProfit] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);

  const { data: doorways, isLoading } = useQuery({
    queryKey: ["doorways", filterCampaign || undefined],
    queryFn: () => api.get("/doorways/", { params: filterCampaign ? { campaign_id: +filterCampaign } : {} }).then((r) => r.data),
  });
  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api.get("/campaigns/").then((r) => r.data),
  });
  const { data: domains } = useQuery({
    queryKey: ["domains"],
    queryFn: () => api.get("/domains/").then((r) => r.data),
  });
  const { data: doorwaysMetrics } = useQuery({
    queryKey: ["analytics-doorways-metrics", 30],
    queryFn: () => api.get("/analytics/doorways-metrics", { params: { days: 30 } }).then((r) => r.data),
  });
  const metricsByDoorway = useMemo(() => {
    const map = new Map<number, DoorwayMetric>();
    (doorwaysMetrics?.doorways ?? []).forEach((m: DoorwayMetric) => map.set(m.doorway_id, m));
    return map;
  }, [doorwaysMetrics]);

  const filtered = useMemo(() => {
    if (!doorways) return [];
    let list = doorways as Doorway[];
    if (filterCampaign) list = list.filter((d) => String(d.campaign_id) === filterCampaign);
    if (filterDomain) list = list.filter((d) => String(d.domain_id) === filterDomain);
    if (filterProfit) {
      list = list.filter((d) => (metricsByDoorway.get(d.id)?.profit_status ?? "no_traffic") === filterProfit);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((d) => (d.path || "").toLowerCase().includes(q) || (d.title || "").toLowerCase().includes(q));
    }
    return list;
  }, [doorways, filterCampaign, filterDomain, filterProfit, searchQuery, metricsByDoorway]);

  const totalPages = Math.ceil(filtered.length / PER_PAGE) || 1;
  const paginated = useMemo(
    () => filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE),
    [filtered, page]
  );

  const generateMut = useMutation({
    mutationFn: (d: typeof gen) => api.post("/doorways/generate", d).then((r) => r.data),
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["doorways"] });
      if (data.doorway_id) {
        toast.success("Дорвей создан", { description: `ID: ${data.doorway_id}` });
        setWizardStep(2);
      }
    },
    onError: () => toast.error("Ошибка генерации"),
  });
  const deployMut = useMutation({
    mutationFn: (id: number) => api.post(`/deploy/doorway/${id}`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success("Деплой выполнен");
    },
    onError: () => toast.error("Ошибка деплоя"),
  });
  const batchMut = useMutation({
    mutationFn: (items: { campaign_id: number; domain_id: number; keyword: string; path: string }[]) =>
      api.post("/doorways/generate-batch", { items }).then((r) => r.data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success(`Создано ${data.created} дорвеев`);
    },
    onError: () => toast.error("Ошибка пакетной генерации"),
  });
  const rollbackMut = useMutation({
    mutationFn: (id: number) => api.post(`/optimizer/doorway/${id}/rollback`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success("Откат выполнен");
    },
    onError: () => toast.error("Ошибка отката"),
  });
  const recsDoorway = useMemo(
    () => (doorways as Doorway[] | undefined)?.find((d) => d.id === recsDoorwayId),
    [doorways, recsDoorwayId]
  );
  const { data: recs } = useQuery({
    queryKey: ["recommendations", recsDoorwayId],
    queryFn: () => api.get(`/optimizer/doorway/${recsDoorwayId}/recommendations?days=14`).then((r) => r.data),
    enabled: !!recsDoorwayId,
  });
  const { data: pauseRecs } = useQuery({
    queryKey: ["pause-recommendations", recsDoorwayId],
    queryFn: () => api.get(`/optimizer/doorway/${recsDoorwayId}/pause-recommendations?days=14`).then((r) => r.data),
    enabled: !!recsDoorwayId && recsDoorway?.status === "paused",
  });
  const applyRecMut = useMutation({
    mutationFn: ({ id, rec }: { id: number; rec: Rec }) =>
      api.post(`/optimizer/doorway/${id}/apply-recommendation`, { rec_type: rec.type, rec_text: rec.text }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      qc.invalidateQueries({ queryKey: ["recommendations", recsDoorwayId] });
      qc.invalidateQueries({ queryKey: ["pause-recommendations", recsDoorwayId] });
      toast.success("Рекомендация применена");
    },
  });

  const { data: qualityCheck } = useQuery({
    queryKey: ["quality-check", panelDoorwayId],
    queryFn: () => api.get(`/doorways/${panelDoorwayId}/quality-check`).then((r) => r.data),
    enabled: !!panelDoorwayId && panelType === "quality",
  });
  const { data: deployCheck } = useQuery({
    queryKey: ["quality-check", deployDoorwayId],
    queryFn: () => api.get(`/doorways/${deployDoorwayId}/quality-check`).then((r) => r.data),
    enabled: !!deployDoorwayId,
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["broken-links", panelDoorwayId] });
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success("Ссылки исправлены");
    },
  });
  const addVariantMut = useMutation({
    mutationFn: (id: number) => api.post(`/doorways/${id}/add-variant`).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success("Вариант добавлен");
    },
    onError: () => toast.error("Ошибка добавления варианта"),
  });
  const applyVariantMut = useMutation({
    mutationFn: ({ id, variant_index }: { id: number; variant_index: number }) =>
      api.post(`/doorways/${id}/apply-variant`, { variant_index }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success("Вариант применён");
      setVariantsDoorwayId(null);
    },
    onError: () => toast.error("Ошибка применения варианта"),
  });

  const openPanel = (id: number, type: "quality" | "predict" | "broken") => {
    setPanelDoorwayId(id);
    setPanelType(type);
  };
  const closePanel = () => { setPanelDoorwayId(null); setPanelType(null); };

  const getLiveUrl = (d: Doorway) => {
    const dom = domains?.find((x: { id: number }) => x.id === d.domain_id) as { domain: string } | undefined;
    if (!dom?.domain) return null;
    const path = (d.path || "/").replace(/^\//, "") ? `/${(d.path || "/").replace(/^\//, "")}` : "";
    return `https://${dom.domain}${path}`;
  };

  const campaignName = (id: number) => campaigns?.find((c: { id: number; name: string }) => c.id === id)?.name ?? id;

  const runBatch = () => {
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
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Дорвеи</h1>
        <Button onClick={() => { setShowGenerate(!showGenerate); if (!showGenerate) { setWizardStep(0); setResult(null); } }}>
          {showGenerate ? "Скрыть" : "Сгенерировать"}
        </Button>
      </div>

      {showGenerate && (
        <div className="mb-6 card-volumetric p-6 animate-scale-in">
          <div className="flex items-center gap-2 mb-6">
            {[1, 2, 3].map((s) => (
              <span key={s} className="flex items-center gap-1">
                <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${wizardStep >= s - 1 ? "bg-emerald-600 text-white" : "bg-slate-700 text-slate-500"}`}>
                  {s}
                </span>
                {s < 3 && <ChevronRight size={16} className="text-slate-600" />}
              </span>
            ))}
            <span className="ml-2 text-slate-500 text-sm">
              {wizardStep === 0 ? "Кампания и домен" : wizardStep === 1 ? "Ключевые слова" : "Превью и деплой"}
            </span>
          </div>

          {wizardStep === 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-slate-400 text-sm mb-1">Кампания</label>
                <Select value={gen.campaign_id} onChange={(e) => setGen((g) => ({ ...g, campaign_id: +e.target.value }))}>
                  {campaigns?.map((c: { id: number; name: string }) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  {!campaigns?.length && <option value={1}>—</option>}
                </Select>
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Домен</label>
                <Select value={gen.domain_id} onChange={(e) => setGen((g) => ({ ...g, domain_id: +e.target.value }))}>
                  {domains?.map((d: { id: number; domain: string }) => <option key={d.id} value={d.id}>{d.domain}</option>)}
                  {!domains?.length && <option value={1}>—</option>}
                </Select>
              </div>
              <div className="md:col-span-2 flex justify-end">
                <Button onClick={() => setWizardStep(1)} disabled={!campaigns?.length || !domains?.length}>
                  Далее
                </Button>
              </div>
            </div>
          )}

          {wizardStep === 1 && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Ключевое слово</label>
                  <Input value={gen.keyword} onChange={(e) => setGen((g) => ({ ...g, keyword: e.target.value }))} placeholder="кредит наличными" />
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Путь</label>
                  <Input value={gen.path} onChange={(e) => setGen((g) => ({ ...g, path: e.target.value || "/" }))} placeholder="/" />
                </div>
              </div>
              <div className="p-4 bg-slate-900/50 rounded-lg">
                <label className="block text-slate-400 text-sm mb-2">Пакетная генерация (по 1 ключу на строку)</label>
                <textarea
                  value={batchKeywords}
                  onChange={(e) => setBatchKeywords(e.target.value)}
                  placeholder="кредит наличными&#10;займ онлайн&#10;микрозайм"
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm"
                />
                <Button variant="secondary" size="sm" className="mt-2" onClick={runBatch} disabled={batchMut.isPending || !batchKeywords.trim()}>
                  {batchMut.isPending ? "Генерация..." : "Сгенерировать пакет"}
                </Button>
                {batchMut.data && <p className="mt-2 text-slate-400 text-sm">Создано: {batchMut.data.created}</p>}
              </div>
              <div className="flex items-center gap-4 flex-wrap">
                <label className="flex items-center gap-2 text-slate-300">
                  <input type="checkbox" checked={gen.save} onChange={(e) => setGen((g) => ({ ...g, save: e.target.checked }))} className="rounded" />
                  Сохранить в базу
                </label>
                <label className="flex items-center gap-2 text-slate-300">
                  <input type="checkbox" checked={gen.generate_faq} onChange={(e) => setGen((g) => ({ ...g, generate_faq: e.target.checked }))} className="rounded" />
                  Сгенерировать FAQ (3–5 вопросов)
                </label>
                <Button onClick={() => generateMut.mutate(gen)} disabled={!gen.keyword.trim() || generateMut.isPending}>
                  {generateMut.isPending ? "Генерация..." : "Сгенерировать"}
                </Button>
                <Button variant="ghost" onClick={() => setWizardStep(0)}>Назад</Button>
              </div>
              {generateMut.error && <p className="text-red-400 text-sm">Ошибка</p>}
              {result?.validation_violations?.length ? (
                <p className="text-amber-400 text-sm">Нарушения: {result.validation_violations.join(", ")}</p>
              ) : null}
            </div>
          )}

          {wizardStep === 2 && result?.html && (
            <div className="space-y-4">
              <p className="text-slate-400 text-sm">
                {result.doorway_id ? `Создан дорвей #${result.doorway_id}` : "Превью"}
              </p>
              <iframe srcDoc={result.html} title="Preview" className="w-full h-80 border border-slate-600 rounded-lg bg-white" sandbox="allow-same-origin" />
              {result.doorway_id && (
                <Button onClick={() => { setDeployDoorwayId(result.doorway_id!); setShowGenerate(false); setResult(null); setWizardStep(0); }}>
                  Задеплоить
                </Button>
              )}
              <Button variant="ghost" onClick={() => { setResult(null); setWizardStep(1); }}>Создать ещё</Button>
            </div>
          )}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-4 mb-4 transition-all duration-200">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={18} />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Поиск по пути или заголовку..."
            className="pl-10"
          />
        </div>
        <Select value={filterCampaign} onChange={(e) => { setFilterCampaign(e.target.value); setPage(1); }} className="w-full sm:w-48">
          <option value="">Все кампании</option>
          {campaigns?.map((c: { id: number; name: string }) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Select>
        <Select value={filterDomain} onChange={(e) => { setFilterDomain(e.target.value); setPage(1); }} className="w-full sm:w-48">
          <option value="">Все домены</option>
          {domains?.map((d: { id: number; domain: string }) => <option key={d.id} value={d.id}>{d.domain}</option>)}
        </Select>
        <Select value={filterProfit} onChange={(e) => { setFilterProfit(e.target.value); setPage(1); }} className="w-full sm:w-44">
          <option value="">Прибыльность: все</option>
          <option value="profitable">Прибыльные</option>
          <option value="unprofitable">Убыточные</option>
          <option value="no_traffic">Без трафика</option>
        </Select>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : !doorways?.length ? (
        <EmptyState
          icon={FileText}
          title="Нет дорвеев"
          description="Создайте первый дорвей с помощью AI-генерации"
          action={<Button onClick={() => setShowGenerate(true)}>Сгенерировать</Button>}
        />
      ) : (
        <div className="card-volumetric overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Кампания</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Путь</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Здоровье</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Статус</th>
                  <th className="text-right px-4 py-3 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {paginated.map((d: Doorway, idx: number) => {
                  const liveUrl = getLiveUrl(d);
                  const metric = metricsByDoorway.get(d.id);
                  const health = metric?.health_score ?? 0;
                  const profitStatus = metric?.profit_status ?? "no_traffic";
                  const profitLabel = profitStatus === "profitable" ? "Прибыльный" : profitStatus === "unprofitable" ? "Убыточный" : "Без трафика";
                  const profitColor = profitStatus === "profitable" ? "text-emerald-400" : profitStatus === "unprofitable" ? "text-amber-400" : "text-slate-500";
                  return (
                    <tr
                      key={d.id}
                      className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-all duration-200 animate-fade-in-up"
                      style={{ animationDelay: `${Math.min(idx * 40, 200)}ms` }}
                    >
                      <td className="px-4 py-3 text-white font-mono text-sm">{d.id}</td>
                      <td className="px-4 py-3 text-slate-400">{campaignName(d.campaign_id)}</td>
                      <td className="px-4 py-3 text-white">{d.path || "/"}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-2">
                            <div
                              className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all duration-200 shrink-0"
                              style={{
                                borderColor: health >= 60 ? "#34d399" : health >= 35 ? "#fbbf24" : "#64748b",
                                color: health >= 60 ? "#34d399" : health >= 35 ? "#fbbf24" : "#94a3b8",
                              }}
                              title={`Скоринг: ${health}/100`}
                            >
                              {health}
                            </div>
                            <div className="min-w-0">
                              <span className={`text-xs font-medium ${profitColor}`}>
                                {profitStatus === "profitable" && <TrendingUp size={12} className="inline mr-0.5" />}
                                {profitStatus === "unprofitable" && <TrendingDown size={12} className="inline mr-0.5" />}
                                {profitStatus === "no_traffic" && <Minus size={12} className="inline mr-0.5" />}
                                {profitLabel}
                              </span>
                              {metric?.profit_probability && (
                                <span className="block text-[10px] text-slate-500 mt-0.5">
                                  Вероятность прибыли: {metric.profit_probability === "high" ? "высокая" : metric.profit_probability === "medium" ? "средняя" : "низкая"}
                                </span>
                              )}
                              {(metric?.above_benchmark_cr != null || metric?.above_benchmark_roi != null) && (
                                <span
                                  className="block text-[10px] text-slate-500 mt-0.5 cursor-help"
                                  title={`Сравнение с средним по кампании. CR — конверсия (%), RPC — выручка на клик. ↑ выше бенчмарка, ↓ ниже.${metric?.benchmark_cr != null ? ` Бенчмарк CR: ${metric.benchmark_cr}%.` : ""}${metric?.benchmark_roi != null ? ` Бенчмарк RPC: ${metric.benchmark_roi}` : ""}`}
                                >
                                  Бенчмарк: CR {metric?.above_benchmark_cr === true ? "↑" : metric?.above_benchmark_cr === false ? "↓" : "—"} RPC {metric?.above_benchmark_roi === true ? "↑" : metric?.above_benchmark_roi === false ? "↓" : "—"}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-0.5">
                          <span className={`px-2 py-1 rounded text-xs font-medium inline-flex w-fit ${
                            d.status === "deployed" || d.status === "indexed" ? "bg-emerald-500/20 text-emerald-400" :
                            d.status === "paused" ? "bg-amber-500/20 text-amber-400" :
                            "bg-slate-600 text-slate-300"
                          }`}>
                            {STATUS_LABELS[d.status] ?? d.status}
                          </span>
                          {d.status === "paused" && d.pause_reason && (
                            <span className="text-slate-500 text-xs max-w-[220px] truncate" title={d.pause_reason}>
                              {d.pause_reason}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {liveUrl && (d.status === "deployed" || d.status === "indexed") && (
                            <a href={liveUrl} target="_blank" rel="noopener noreferrer" className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-emerald-400" title="Открыть">
                              <ExternalLink size={18} />
                            </a>
                          )}
                          <DropdownMenu
                            align="right"
                            trigger={<button className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white"><MoreVertical size={18} /></button>}
                          >
                            {d.status !== "deployed" && d.status !== "indexed" && (
                              <DropdownMenuItem onClick={() => setDeployDoorwayId(d.id)}>Деплой</DropdownMenuItem>
                            )}
                            <DropdownMenuItem onClick={() => setRecsDoorwayId(recsDoorwayId === d.id ? null : d.id)}>Рекомендации</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setVariantsDoorwayId(variantsDoorwayId === d.id ? null : d.id)}>
                              <Layers size={14} className="mr-2" /> Варианты A/B
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPanel(d.id, "quality")}>Quality</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPanel(d.id, "predict")}>Predict CR</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPanel(d.id, "broken")}>Битые ссылки</DropdownMenuItem>
                            <DropdownMenuItem variant="danger" onClick={() => rollbackMut.mutate(d.id)}>Rollback</DropdownMenuItem>
                          </DropdownMenu>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700">
              <span className="text-slate-500 text-sm">
                {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, filtered.length)} из {filtered.length}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}>
                  <ChevronLeft size={16} />
                </Button>
                <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}>
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {panelDoorwayId && panelType && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={closePanel}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-3 flex justify-between">
              <span>{panelType === "quality" ? "Quality Check" : panelType === "predict" ? "Predict CR" : "Битые ссылки"} — дорвей #{panelDoorwayId}</span>
              <button onClick={closePanel} className="text-slate-400 hover:text-white">✕</button>
            </h2>
            {panelType === "quality" && (
              qualityCheck ? (
                <div className="space-y-2 text-sm">
                  <p className={qualityCheck.ok ? "text-emerald-400" : "text-amber-400"}>{qualityCheck.ok ? "✓ Прошёл проверку" : "⚠ Есть замечания"}</p>
                  {qualityCheck.errors?.length ? <p className="text-red-400">Ошибки: {qualityCheck.errors.join(", ")}</p> : null}
                  {qualityCheck.warnings?.length ? <p className="text-amber-400">Предупреждения: {qualityCheck.warnings.join(", ")}</p> : null}
                </div>
              ) : <Skeleton className="h-8 w-full" />
            )}
            {panelType === "predict" && (
              predictCr ? <pre className="text-slate-300 text-sm whitespace-pre-wrap font-mono">{JSON.stringify(predictCr, null, 2)}</pre> : <Skeleton className="h-24 w-full" />
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
                          {broken.map((url: string, i: number) => <li key={i} className="truncate font-mono">{url}</li>)}
                        </ul>
                        <div className="flex gap-2 items-center">
                          <Input id="replacement" placeholder="Замена (по умолчанию #)" className="flex-1" />
                          <Button size="sm" onClick={() => {
                            const inp = document.getElementById("replacement") as HTMLInputElement;
                            repairMut.mutate({ id: panelDoorwayId!, data: { broken_urls: broken, replacement: inp?.value || "#" } });
                          }} disabled={repairMut.isPending}>Исправить</Button>
                        </div>
                      </>
                    ) : <p className="text-emerald-400 text-sm">Битых ссылок не найдено</p>;
                  })()}
                </div>
              ) : <Skeleton className="h-16 w-full" />
            )}
          </div>
        </div>
      )}

      {variantsDoorwayId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setVariantsDoorwayId(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-xl w-full mx-4 max-h-[80vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4 flex justify-between">
              <span>Варианты A/B — дорвей #{variantsDoorwayId}</span>
              <button onClick={() => setVariantsDoorwayId(null)} className="text-slate-400 hover:text-white">✕</button>
            </h2>
            {(() => {
              const dw = doorways?.find((d: Doorway) => d.id === variantsDoorwayId) as Doorway | undefined;
              const variants = dw?.content_variants ?? [];
              return (
                <div className="space-y-4">
                  <div className="p-3 bg-slate-700/50 rounded-lg">
                    <p className="text-slate-400 text-xs mb-1">Основной контент</p>
                    <p className="text-white text-sm truncate">{dw?.title ?? "—"}</p>
                  </div>
                  {variants.map((v: ContentVariant, i: number) => (
                    <div key={i} className="flex items-center justify-between gap-3 p-3 bg-slate-700/50 rounded-lg">
                      <div className="min-w-0 flex-1">
                        <p className="text-slate-400 text-xs mb-1">Вариант {i + 1}</p>
                        <p className="text-white text-sm truncate">{v.title ?? "—"}</p>
                      </div>
                      <Button size="sm" onClick={() => applyVariantMut.mutate({ id: variantsDoorwayId!, variant_index: i })} disabled={applyVariantMut.isPending}>
                        <Check size={14} className="mr-1" /> Применить
                      </Button>
                    </div>
                  ))}
                  <Button onClick={() => addVariantMut.mutate(variantsDoorwayId!)} disabled={addVariantMut.isPending} className="w-full">
                    <Plus size={16} className="mr-2" /> Добавить вариант
                  </Button>
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {deployDoorwayId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setDeployDoorwayId(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-md w-full mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-4 flex justify-between">
              <span>Проверка перед деплоем — дорвей #{deployDoorwayId}</span>
              <button onClick={() => setDeployDoorwayId(null)} className="text-slate-400 hover:text-white">✕</button>
            </h2>
            {deployCheck ? (
              <div className="space-y-3">
                <p className={deployCheck.ok ? "text-emerald-400 text-sm" : "text-amber-400 text-sm"}>
                  {deployCheck.ok ? "✓ Готов к деплою" : "⚠ Есть замечания (можно деплоить)"}
                </p>
                {deployCheck.errors?.length ? (
                  <ul className="text-red-400 text-sm space-y-1">
                    {deployCheck.errors.map((e: string, i: number) => <li key={i}>• {e}</li>)}
                  </ul>
                ) : null}
                {deployCheck.warnings?.length ? (
                  <ul className="text-amber-400 text-sm space-y-1">
                    {deployCheck.warnings.map((w: string, i: number) => <li key={i}>• {w}</li>)}
                  </ul>
                ) : null}
                <div className="flex gap-2 pt-2">
                  <Button onClick={() => setDeployDoorwayId(null)} variant="secondary">Отмена</Button>
                  <Button onClick={() => { deployMut.mutate(deployDoorwayId); setDeployDoorwayId(null); }} disabled={deployMut.isPending}>
                    {deployMut.isPending ? "Деплой..." : "Деплоить"}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-slate-400 text-sm">Загрузка проверки...</p>
            )}
          </div>
        </div>
      )}

      {recsDoorwayId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setRecsDoorwayId(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-5 max-w-lg w-full mx-4 max-h-[85vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-3 flex justify-between">
              <span>Рекомендации — дорвей #{recsDoorwayId}</span>
              <button onClick={() => setRecsDoorwayId(null)} className="text-slate-400 hover:text-white">✕</button>
            </h2>
            {recsDoorway?.status === "paused" && Array.isArray(pauseRecs) && pauseRecs.length > 0 && (
              <div className="mb-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl shadow-lg animate-scale-in" title="Рекомендации построены по прибыльным дорвеям этой кампании">
                <p className="text-amber-400 text-xs font-medium mb-2">По данным кампании (дорвей на паузе)</p>
                <ul className="space-y-2">
                  {pauseRecs.map((pr: { type: string; text: string; layout_index?: number; winner_cr?: number }, i: number) => (
                    <li key={i} className="text-slate-300 text-sm">{pr.text}</li>
                  ))}
                </ul>
                <p className="text-slate-500 text-xs mt-3">RPC — выручка на клик. Примените лучший вариант в меню «Варианты A/B» для этого дорвея.</p>
              </div>
            )}
            {recs?.length ? (
              <>
                {recsDoorway?.status === "paused" && pauseRecs?.length ? <p className="text-slate-400 text-xs mb-2">Рекомендации AI</p> : null}
                <ul className="space-y-3">
                  {recs.map((r: Rec, i: number) => (
                    <li key={i} className="flex items-start justify-between gap-3 p-2 bg-slate-700/50 rounded-lg">
                      <span className="text-slate-300 text-sm">{r.text}</span>
                      <Button size="sm" onClick={() => applyRecMut.mutate({ id: recsDoorwayId!, rec: r })} disabled={applyRecMut.isPending || r.type === "info"}>
                        {r.type === "info" ? "—" : "Применить"}
                      </Button>
                    </li>
                  ))}
                </ul>
              </>
            ) : recs === undefined && !pauseRecs?.length ? (
              <p className="text-slate-400 text-sm">Загрузка...</p>
            ) : !recs?.length ? (
              <p className="text-slate-400 text-sm">Нет AI-рекомендаций</p>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
