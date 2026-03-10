import { useState, useMemo, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { EmptyState } from "../components/ui/empty-state";
import { Skeleton } from "../components/ui/skeleton";
import { DropdownMenu, DropdownMenuItem } from "../components/ui/dropdown-menu";
import { FileText, MoreVertical, ExternalLink, ChevronRight, Search, Layers, Plus, Check, TrendingUp, TrendingDown, Minus } from "lucide-react";

type Rec = { type: string; text: string };
type ContentVariant = { title?: string; content?: string; meta_description?: string };
type Doorway = { id: number; campaign_id: number; domain_id: number; path: string; title?: string; status: string; content_variants?: ContentVariant[]; pause_reason?: string | null; cloaking_rules?: { quiz?: { enabled?: boolean; questions?: unknown[] } } };
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

const FIX_CODE_LABELS: Record<string, string> = {
  meta_short: "Meta 80+ символов",
  keyword_not_in_title: "Ключ в заголовке",
  keyword_not_in_content: "Ключ в контенте",
  no_urgency_social_proof: "Urgency / Social proof",
  no_faq: "Сгенерировать FAQ",
};

const GEO_OPTIONS = ["US", "DE", "PL", "RU", "GB", "FR", "ES", "IT", "UA", "KZ", "BY", "TR", "BR", "MX", "CA", "AU", "NL"];

const PER_PAGE = 500;

function loadTaskIds(key: string): string[] {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw) as unknown;
      if (Array.isArray(parsed)) return parsed.filter((x): x is string => typeof x === "string");
      if (typeof parsed === "string" && parsed) return [parsed];
    }
    const legacy = sessionStorage.getItem(key.replace("_ids", "_id"));
    if (legacy) return [legacy];
  } catch {
    /* ignore */
  }
  return [];
}

function saveTaskIds(key: string, ids: string[]) {
  try {
    if (ids.length) sessionStorage.setItem(key, JSON.stringify(ids));
    else sessionStorage.removeItem(key);
    sessionStorage.removeItem(key.replace("_ids", "_id"));
  } catch {
    /* ignore */
  }
}

export type ProcessType = "generate" | "deploy" | "delete";

export default function Doorways() {
  const qc = useQueryClient();
  const [wizardStep, setWizardStep] = useState(0);
  const [showGenerate, setShowGenerate] = useState(false);
  const [deployDoorwayId, setDeployDoorwayId] = useState<number | null>(null);
  const [gen, setGen] = useState({ campaign_id: 1, domain_id: 1, keyword: "", path: "/", save: true, generate_faq: false, generate_quiz: false, target_geos: [] as string[] });
  const [batchKeywords, setBatchKeywords] = useState("");
  const [result, setResult] = useState<{ html?: string; doorway_id?: number; validation_violations?: string[] } | null>(null);
  const [recsDoorwayId, setRecsDoorwayId] = useState<number | null>(null);
  const [panelDoorwayId, setPanelDoorwayId] = useState<number | null>(null);
  const [panelType, setPanelType] = useState<"quality" | "predict" | "broken" | "forecast" | "sources" | null>(null);
  const [variantsDoorwayId, setVariantsDoorwayId] = useState<number | null>(null);
  const [filterCampaign, setFilterCampaign] = useState<string>("");
  const [filterDomain, setFilterDomain] = useState<string>("");
  const [filterProfit, setFilterProfit] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<"" | "health" | "revenue">("");
  const [cloneDoorwayId, setCloneDoorwayId] = useState<number | null>(null);
  const [cloneDomainId, setCloneDomainId] = useState<number>(0);
  const [clonePath, setClonePath] = useState("/");
  const [selectedDoorwayIds, setSelectedDoorwayIds] = useState<Set<number>>(new Set());
  const [selectForDeployN, setSelectForDeployN] = useState(150);
  const [batchQualityResults, setBatchQualityResults] = useState<Array<{ doorway_id: number; path: string; title: string; ok: boolean; errors: string[]; warnings: string[]; warning_codes?: { code: string; message: string }[] }> | null>(null);
  const [qualityApplySelectedIds, setQualityApplySelectedIds] = useState<Set<number>>(new Set());
  const [qualityApplyFixCodes, setQualityApplyFixCodes] = useState<Set<string>>(new Set());
  const [batchDeployTaskIds, setBatchDeployTaskIdsState] = useState<string[]>(() => loadTaskIds("dorvey_batch_deploy_task_ids"));
  const setBatchDeployTaskIds = (ids: string[]) => {
    setBatchDeployTaskIdsState(ids);
    saveTaskIds("dorvey_batch_deploy_task_ids", ids);
  };
  const addDeployTaskId = (id: string) => setBatchDeployTaskIds([...batchDeployTaskIds, id]);
  const removeDeployTaskId = (id: string) => setBatchDeployTaskIds(batchDeployTaskIds.filter((x) => x !== id));

  const [batchDeleteTaskIds, setBatchDeleteTaskIdsState] = useState<string[]>(() => loadTaskIds("dorvey_batch_delete_task_ids"));
  const setBatchDeleteTaskIds = (ids: string[]) => {
    setBatchDeleteTaskIdsState(ids);
    saveTaskIds("dorvey_batch_delete_task_ids", ids);
  };
  const addDeleteTaskId = (id: string) => setBatchDeleteTaskIds([...batchDeleteTaskIds, id]);
  const removeDeleteTaskId = (id: string) => setBatchDeleteTaskIds(batchDeleteTaskIds.filter((x) => x !== id));

  const [batchGenerateTaskIds, setBatchGenerateTaskIdsState] = useState<string[]>(() => loadTaskIds("dorvey_batch_generate_task_ids"));
  const setBatchGenerateTaskIds = (ids: string[]) => {
    setBatchGenerateTaskIdsState(ids);
    saveTaskIds("dorvey_batch_generate_task_ids", ids);
  };
  const addGenerateTaskId = (id: string) => setBatchGenerateTaskIds([...batchGenerateTaskIds, id]);
  const removeGenerateTaskId = (id: string) => setBatchGenerateTaskIds(batchGenerateTaskIds.filter((x) => x !== id));

  const [openProcess, setOpenProcess] = useState<{ type: ProcessType; task_id: string } | null>(null);

  const { data: activeBatchTasks, refetch: refetchActiveBatchTasks } = useQuery({
    queryKey: ["active-batch-tasks"],
    queryFn: () => api.get("/doorways/active-batch-tasks").then((r) => r.data as { deploy?: string[]; generate?: string[]; delete?: string[] }),
    refetchOnWindowFocus: true,
  });
  useEffect(() => {
    if (!activeBatchTasks) return;
    if (Array.isArray(activeBatchTasks.deploy)) {
      setBatchDeployTaskIdsState(activeBatchTasks.deploy);
      saveTaskIds("dorvey_batch_deploy_task_ids", activeBatchTasks.deploy);
    }
    if (Array.isArray(activeBatchTasks.generate)) {
      setBatchGenerateTaskIdsState(activeBatchTasks.generate);
      saveTaskIds("dorvey_batch_generate_task_ids", activeBatchTasks.generate);
    }
    if (Array.isArray(activeBatchTasks.delete)) {
      setBatchDeleteTaskIdsState(activeBatchTasks.delete);
      saveTaskIds("dorvey_batch_delete_task_ids", activeBatchTasks.delete);
    }
  }, [activeBatchTasks]);

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
  const { data: campaignKeywords } = useQuery({
    queryKey: ["keywords", gen.campaign_id],
    queryFn: () => api.get("/keywords/", { params: { campaign_id: gen.campaign_id } }).then((r) => r.data),
    enabled: !!gen.campaign_id && wizardStep === 1,
  });
  const { data: offerGeos } = useQuery({
    queryKey: ["keywords", "offer-geos", gen.campaign_id],
    queryFn: () => api.get("/keywords/suggest-by-offers-geo", { params: { campaign_id: gen.campaign_id } }).then((r) => r.data as { geos?: string[] }),
    enabled: !!gen.campaign_id && (wizardStep === 0 || wizardStep === 1),
  });
  const { data: doorwaysMetrics } = useQuery({
    queryKey: ["analytics-doorways-metrics", 30],
    queryFn: () => api.get("/analytics/doorways-metrics", { params: { days: 30 } }).then((r) => r.data),
  });
  const { data: earlyDoorways } = useQuery({
    queryKey: ["analytics-early-doorways", 3, 20],
    queryFn: () => api.get("/analytics/early-doorways", { params: { days: 3, min_clicks: 20 } }).then((r) => r.data),
  });
  const { data: processStatus, refetch: refetchProcessStatus, isError: processStatusError } = useQuery({
    queryKey: ["process-status", openProcess?.type, openProcess?.task_id],
    queryFn: async () => {
      if (!openProcess) return null;
      if (openProcess.type === "deploy") {
        return api.get(`/deploy/batch/${openProcess.task_id}/status`).then((r) => ({ type: "deploy" as const, ...r.data }));
      }
      if (openProcess.type === "generate") {
        return api.get(`/doorways/generate-batch/${openProcess.task_id}/status`).then((r) => ({ type: "generate" as const, ...r.data }));
      }
      if (openProcess.type === "delete") {
        return api.get(`/doorways/batch-delete/${openProcess.task_id}/status`).then((r) => ({ type: "delete" as const, ...r.data }));
      }
      return null;
    },
    enabled: !!openProcess?.type && !!openProcess?.task_id,
    refetchInterval: (query) => {
      const d = query.state.data as { status?: string } | undefined;
      return d && (d.status === "running" || d.status === "paused" || d.status === "queued") ? 2500 : false;
    },
  });
  const metricsByDoorway = useMemo(() => {
    const map = new Map<number, DoorwayMetric>();
    (doorwaysMetrics?.doorways ?? []).forEach((m: DoorwayMetric) => map.set(m.doorway_id, m));
    return map;
  }, [doorwaysMetrics]);
  const qualityUniqueFixCodes = useMemo(() => {
    if (!batchQualityResults?.length) return [];
    const set = new Set<string>();
    batchQualityResults.forEach((r) => (r.warning_codes || []).forEach((w: { code: string }) => set.add(w.code)));
    return Array.from(set).filter((code) => code in FIX_CODE_LABELS);
  }, [batchQualityResults]);

  const batchDeployStatusByDoorwayId = useMemo(() => {
    if (openProcess?.type !== "deploy" || !processStatus?.results?.length) return new Map<number, string>();
    const m = new Map<number, string>();
    (processStatus.results as { doorway_id: number; status: string }[]).forEach((r) => m.set(r.doorway_id, r.status));
    return m;
  }, [openProcess?.type, openProcess?.task_id, processStatus?.results]);

  const batchGenerateCompletedToastRef = useRef<string | null>(null);
  useEffect(() => {
    if (openProcess?.type !== "generate" || !processStatus || processStatus.status !== "completed") return;
    if (batchGenerateCompletedToastRef.current === openProcess.task_id) return;
    batchGenerateCompletedToastRef.current = openProcess.task_id;
    qc.invalidateQueries({ queryKey: ["doorways"] });
    const created = (processStatus as { created?: number }).created ?? 0;
    if (created > 0) toast.success(`Пакетная генерация завершена. Создано дорвеев: ${created}`);
  }, [openProcess?.type, openProcess?.task_id, processStatus, qc]);

  const batchDeleteCompletedToastRef = useRef<string | null>(null);
  useEffect(() => {
    if (openProcess?.type !== "delete" || !processStatus || processStatus.status !== "completed") return;
    if (batchDeleteCompletedToastRef.current === openProcess.task_id) return;
    batchDeleteCompletedToastRef.current = openProcess.task_id;
    qc.invalidateQueries({ queryKey: ["doorways"] });
    setSelectedDoorwayIds(new Set());
    const deleted = (processStatus as { deleted?: number }).deleted ?? 0;
    if (deleted > 0) toast.success(`Удалено дорвеев: ${deleted}`);
  }, [openProcess?.type, openProcess?.task_id, processStatus, qc]);

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

  const paginated = useMemo(
    () => filtered.slice(0, PER_PAGE),
    [filtered]
  );

  const generateMut = useMutation({
    mutationFn: (d: typeof gen) => {
      const payload: Record<string, unknown> = { ...d };
      if (d.target_geos.length === 1) payload.target_geo = d.target_geos[0];
      else if (d.target_geos.length > 1) payload.target_geos = d.target_geos;
      delete (payload as { target_geos?: string[] }).target_geos;
      return api.post("/doorways/generate", payload).then((r) => r.data);
    },
    onSuccess: (data: { doorway_id?: number; created_count?: number }) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["doorways"] });
      const count = data.created_count ?? (data.doorway_id ? 1 : 0);
      if (count > 0) {
        toast.success(count > 1 ? `Создано дорвеев: ${count}` : "Дорвей создан", count > 1 ? undefined : { description: `ID: ${data.doorway_id}` });
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
  const fixRootMut = useMutation({
    mutationFn: (domain_id: number) => api.post(`/deploy/domain/${domain_id}/fix-root`).then((r) => r.data),
    onSuccess: (data: { message?: string }) => {
      toast.success((data as { message?: string })?.message ?? "Корень домена обновлён");
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });
  const batchDeployMut = useMutation({
    mutationFn: (doorway_ids: number[]) => api.post("/deploy/batch", { doorway_ids }).then((r) => r.data),
    onSuccess: (data: { status?: string; task_id?: string; doorway_ids?: number[] }) => {
      if (data.task_id) {
        if (data?.task_id) {
          addDeployTaskId(data.task_id);
          setOpenProcess({ type: "deploy", task_id: data.task_id });
        }
      }
      setSelectedDoorwayIds(new Set());
      const n = data.doorway_ids?.length ?? 0;
      toast.success(
        n > 0
          ? `Деплой запущен: ${n} дорвеев. Откройте окно прогресса для паузы или отмены.`
          : "Деплой в очередь.",
        { duration: 5000 }
      );
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e?.response?.data?.detail ?? "Ошибка массового деплоя"),
  });
  const batchDeleteMut = useMutation({
    mutationFn: (doorway_ids: number[]) => api.post("/doorways/batch-delete", { doorway_ids }).then((r) => r.data as { task_id: string; status: string }),
    onSuccess: (data: { task_id?: string }) => {
      if (data?.task_id) {
      if (data?.task_id) {
        addDeleteTaskId(data.task_id);
        setOpenProcess({ type: "delete", task_id: data.task_id });
      }
        toast.success("Удаление запущено");
      }
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e?.response?.data?.detail ?? "Ошибка удаления"),
  });
  const batchQualityMut = useMutation({
    mutationFn: (doorway_ids: number[]) => api.post("/doorways/batch-quality-check", { doorway_ids }).then((r) => r.data),
    onSuccess: (data: { results?: Array<{ doorway_id: number; path: string; title: string; ok: boolean; errors: string[]; warnings: string[]; warning_codes?: { code: string; message: string }[] }> }) => {
      setBatchQualityResults(data.results ?? []);
      setQualityApplySelectedIds(new Set());
      setQualityApplyFixCodes(new Set());
    },
    onError: () => toast.error("Ошибка проверки"),
  });
  const batchApplyWarningsMut = useMutation({
    mutationFn: (payload: { doorway_ids: number[]; fix_codes: string[] }) =>
      api.post("/doorways/batch-apply-warnings", payload, { timeout: 120000 }).then((r) => r.data),
    onSuccess: (data: { applied?: Record<string, number>; errors?: string[] }) => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      const n = Object.values(data.applied || {}).reduce((a, b) => a + b, 0);
      if (n > 0) toast.success(`Применено исправлений: ${n}`);
      if (data.errors?.length) {
        const msg = data.errors.slice(0, 3).join("; ");
        if (n === 0) toast.error(msg); else toast.warning(msg);
      }
    },
    onError: (e: { response?: { data?: { detail?: string; errors?: string[]; message?: string } }; message?: string }) => {
      const d = e?.response?.data;
      const msg = Array.isArray(d?.errors) ? d.errors.slice(0, 2).join("; ") : (typeof d?.detail === "string" ? d.detail : d?.message) || e?.message || "Ошибка применения";
      toast.error(msg);
    },
  });
  const batchMut = useMutation({
    mutationFn: (payload: { items: { campaign_id: number; domain_id: number; keyword: string; path: string; target_geo?: string; target_geos?: string[] }[]; generate_faq?: boolean; generate_quiz?: boolean; target_geos?: string[] }) =>
      api.post("/doorways/generate-batch", payload).then((r) => r.data as { task_id: string; status: string }),
    onSuccess: (data: { task_id?: string }) => {
      if (data?.task_id) {
      if (data?.task_id) {
        addGenerateTaskId(data.task_id);
        setOpenProcess({ type: "generate", task_id: data.task_id });
      }
        toast.success("Пакетная генерация запущена");
      }
    },
    onError: (e: { response?: { data?: { detail?: string; message?: string } }; message?: string }) => {
      const data = e?.response?.data as { detail?: string; message?: string } | undefined;
      const msg = data?.detail ?? data?.message ?? e?.message ?? "Ошибка пакетной генерации";
      toast.error(typeof msg === "string" ? msg : "Ошибка пакетной генерации");
    },
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
  const { data: profitForecast } = useQuery({
    queryKey: ["profit-forecast", panelDoorwayId],
    queryFn: () => api.get(`/analytics/doorway/${panelDoorwayId}/profit-forecast?days=7`).then((r) => r.data),
    enabled: !!panelDoorwayId && panelType === "forecast",
  });
  const { data: trafficBySource } = useQuery({
    queryKey: ["traffic-by-source", panelDoorwayId],
    queryFn: () => api.get(`/analytics/doorway/${panelDoorwayId}/traffic-by-source?days=30`).then((r) => r.data),
    enabled: !!panelDoorwayId && panelType === "sources",
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
  const pauseDoorwayMut = useMutation({
    mutationFn: (id: number) => api.patch(`/doorways/${id}`, { status: "paused" }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      qc.invalidateQueries({ queryKey: ["analytics-early-doorways"] });
      toast.success("Дорвей поставлен на паузу");
    },
    onError: () => toast.error("Ошибка"),
  });
  const quizToggleMut = useMutation({
    mutationFn: ({ id, quiz_enabled }: { id: number; quiz_enabled: boolean }) => api.patch(`/doorways/${id}`, { quiz_enabled }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      toast.success("Квиз обновлён");
    },
    onError: () => toast.error("Ошибка"),
  });
  const generateQuizMut = useMutation({
    mutationFn: (doorwayId: number) => api.post(`/doorways/${doorwayId}/generate-quiz`).then((r) => r.data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["doorways"] }); toast.success("Квиз добавлен"); },
    onError: (e: { response?: { data?: { detail?: string } } }) => toast.error((e?.response?.data as { detail?: string })?.detail ?? "Ошибка генерации квиза"),
  });
  const batchGenerateQuizMut = useMutation({
    mutationFn: (doorway_ids: number[]) => api.post("/doorways/batch-generate-quiz", { doorway_ids }).then((r) => r.data),
    onSuccess: (data: { results?: { doorway_id: number; ok: boolean; error?: string }[] }) => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      const results = data.results ?? [];
      const ok = results.filter((r) => r.ok).length;
      const err = results.filter((r) => !r.ok).length;
      if (ok) toast.success(`Квиз добавлен: ${ok}`);
      if (err) toast.warning(`Ошибки: ${err}`);
    },
    onError: () => toast.error("Ошибка пакетной генерации квиза"),
  });
  const cloneToDomainMut = useMutation({
    mutationFn: ({ id, domain_id, path }: { id: number; domain_id: number; path: string }) =>
      api.post(`/optimizer/doorway/${id}/clone-to-domain`, { domain_id, path }).then((r) => r.data),
    onSuccess: (data: { doorway_id: number; message?: string }) => {
      qc.invalidateQueries({ queryKey: ["doorways"] });
      setCloneDoorwayId(null);
      toast.success(data.message || `Дорвей клонирован: #${data.doorway_id}`);
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e?.response?.data?.detail ?? "Ошибка"),
  });
  const runSslMut = useMutation({
    mutationFn: (doorwayId: number) => api.post(`/deploy/doorway/${doorwayId}/ssl`).then((r) => r.data),
    onSuccess: (data: { message?: string }) => {
      toast.success(data?.message ?? "SSL сертификат получен, HTTPS настроен");
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e?.response?.data?.detail ?? "Ошибка SSL (Certbot)"),
  });

  const openPanel = (id: number, type: "quality" | "predict" | "broken" | "forecast" | "sources") => {
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
    batchMut.mutate({
      items,
      generate_faq: gen.generate_faq,
      generate_quiz: gen.generate_quiz,
      target_geos: gen.target_geos.length > 0 ? gen.target_geos : undefined,
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Дорвеи</h1>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => refetchActiveBatchTasks()}
            className="text-slate-400 hover:text-white text-sm"
            title="Подгрузить активные деплои/генерации с сервера"
          >
            Проверить процессы
          </button>
          <Button onClick={() => { setShowGenerate(!showGenerate); if (!showGenerate) { setWizardStep(0); setResult(null); } }}>
            {showGenerate ? "Скрыть" : "Сгенерировать"}
          </Button>
        </div>
      </div>

      {(batchGenerateTaskIds.length > 0 || batchDeployTaskIds.length > 0 || batchDeleteTaskIds.length > 0) && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/80 px-4 py-2">
          <span className="text-slate-400 text-sm">Процессы:</span>
          {batchGenerateTaskIds.map((task_id, i) => (
            <button
              key={task_id}
              onClick={() => setOpenProcess({ type: "generate", task_id })}
              className={`rounded-lg px-3 py-1.5 text-sm text-white hover:opacity-90 ${openProcess?.type === "generate" && openProcess?.task_id === task_id ? "ring-2 ring-sky-400 bg-sky-600" : "bg-sky-600/80"}`}
            >
              Пакетная генерация {batchGenerateTaskIds.length > 1 ? i + 1 : ""}
            </button>
          ))}
          {batchDeployTaskIds.map((task_id, i) => (
            <button
              key={task_id}
              onClick={() => setOpenProcess({ type: "deploy", task_id })}
              className={`rounded-lg px-3 py-1.5 text-sm text-white hover:opacity-90 ${openProcess?.type === "deploy" && openProcess?.task_id === task_id ? "ring-2 ring-amber-400 bg-amber-600" : "bg-amber-600/80"}`}
            >
              Деплой {batchDeployTaskIds.length > 1 ? i + 1 : ""}
            </button>
          ))}
          {batchDeleteTaskIds.map((task_id, i) => (
            <button
              key={task_id}
              onClick={() => setOpenProcess({ type: "delete", task_id })}
              className={`rounded-lg px-3 py-1.5 text-sm text-white hover:opacity-90 ${openProcess?.type === "delete" && openProcess?.task_id === task_id ? "ring-2 ring-red-400 bg-red-600" : "bg-red-600/80"}`}
            >
              Удаление {batchDeleteTaskIds.length > 1 ? i + 1 : ""}
            </button>
          ))}
          <button
            type="button"
            onClick={() => refetchActiveBatchTasks()}
            className="ml-2 rounded-lg px-2 py-1 text-xs text-slate-400 hover:text-white hover:bg-slate-700"
            title="Подгрузить активные процессы с сервера (другой комп/вкладка)"
          >
            Обновить
          </button>
        </div>
      )}

      {earlyDoorways?.doorways?.length > 0 && (
        <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30">
          <h2 className="text-lg font-medium text-amber-200 mb-2">Первые 48 ч — без конверсий</h2>
          <p className="text-slate-400 text-sm mb-3">
            За последние {earlyDoorways.days} дн. задеплоены, трафик ≥{earlyDoorways.min_clicks} кликов, 0 конверсий. Поставьте на паузу или смените оффер в кампании.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-600">
                  <th className="text-left py-2 text-slate-400 font-medium">ID</th>
                  <th className="text-left py-2 text-slate-400 font-medium">Кампания</th>
                  <th className="text-left py-2 text-slate-400 font-medium">Заголовок</th>
                  <th className="text-left py-2 text-slate-400 font-medium">Клики</th>
                  <th className="text-right py-2 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {(earlyDoorways.doorways as { doorway_id: number; campaign_id: number; title?: string; clicks: number }[]).map((row) => (
                  <tr key={row.doorway_id} className="border-b border-slate-700/50">
                    <td className="py-2 text-white">{row.doorway_id}</td>
                    <td className="py-2 text-slate-300">{campaignName(row.campaign_id)}</td>
                    <td className="py-2 text-slate-400 truncate max-w-[200px]">{row.title || "—"}</td>
                    <td className="py-2 text-amber-400">{row.clicks}</td>
                    <td className="py-2 text-right">
                      <button
                        onClick={() => pauseDoorwayMut.mutate(row.doorway_id)}
                        disabled={pauseDoorwayMut.isPending}
                        className="mr-2 px-2 py-1 bg-slate-600 hover:bg-slate-500 rounded text-white text-xs"
                      >
                        Пауза
                      </button>
                      <Link to={`/offers?campaign_id=${row.campaign_id}`} className="text-amber-400 hover:underline text-xs">Офферы кампании</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
                  <div className="flex gap-2">
                    <Input value={gen.keyword} onChange={(e) => setGen((g) => ({ ...g, keyword: e.target.value }))} placeholder="кредит наличными" className="flex-1" />
                    <Select
                      value=""
                      onChange={(e) => { const v = e.target.value; if (v) setGen((g) => ({ ...g, keyword: v })); }}
                      className="w-48"
                    >
                      <option value="">Из кампании…</option>
                      {(campaignKeywords as { keyword: string; volume: number }[] | undefined)?.slice(0, 30).map((k) => (
                        <option key={k.keyword} value={k.keyword}>{k.keyword} ({k.volume})</option>
                      ))}
                    </Select>
                  </div>
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Путь</label>
                  <Input value={gen.path} onChange={(e) => setGen((g) => ({ ...g, path: e.target.value || "/" }))} placeholder="/" />
                </div>
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Страны (гео)</label>
                <p className="text-slate-500 text-xs mb-2">Пусто — один дорвей (язык кампании). Выберите страны — по каждой создаётся отдельный дорвей с языком страны (path: /en/slug, /de/slug …).</p>
                <div className="flex flex-wrap gap-2">
                  {GEO_OPTIONS.map((code) => (
                    <label key={code} className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-slate-700/80 border border-slate-600 cursor-pointer hover:bg-slate-600/80">
                      <input
                        type="checkbox"
                        checked={gen.target_geos.includes(code)}
                        onChange={(e) => {
                          setGen((g) => ({
                            ...g,
                            target_geos: e.target.checked ? [...g.target_geos, code] : g.target_geos.filter((c) => c !== code),
                          }));
                        }}
                        className="rounded"
                      />
                      <span className="text-sm text-white">{code}</span>
                    </label>
                  ))}
                </div>
                {offerGeos?.geos?.length ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 text-slate-400"
                    onClick={() => setGen((g) => ({ ...g, target_geos: [...new Set([...(offerGeos.geos || []), ...g.target_geos])] }))}
                  >
                    Подставить все гео офферов ({offerGeos.geos.join(", ")})
                  </Button>
                ) : null}
              </div>
              <div className="p-4 bg-slate-900/50 rounded-lg">
                <label className="block text-slate-400 text-sm mb-2">Пакетная генерация (по 1 ключу на строку, сортировка по объёму)</label>
                <div className="flex gap-2 mb-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      const kws = (campaignKeywords as { keyword: string; volume: number }[] | undefined) ?? [];
                      setBatchKeywords(kws.map((k) => k.keyword).join("\n"));
                    }}
                    disabled={!campaignKeywords?.length}
                  >
                    Загрузить из кампании ({campaignKeywords?.length ?? 0} ключей)
                  </Button>
                </div>
                <textarea
                  value={batchKeywords}
                  onChange={(e) => setBatchKeywords(e.target.value)}
                  placeholder="кредит наличными&#10;займ онлайн&#10;микрозайм"
                  rows={3}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500 text-sm"
                />
                <Button variant="secondary" size="sm" className="mt-2" onClick={runBatch} disabled={batchMut.isPending || !batchKeywords.trim()}>
                  {batchMut.isPending ? "Запуск…" : "Сгенерировать пакет"}
                </Button>
                {batchGenerateTaskIds.length > 0 && !(openProcess?.type === "generate") && (
                  <p className="mt-2 text-amber-400 text-sm">Генерация на сервере. <button type="button" onClick={() => setOpenProcess({ type: "generate", task_id: batchGenerateTaskIds[0] })} className="underline">Открыть прогресс</button></p>
                )}
                {batchGenerateTaskIds.length > 0 && openProcess?.type === "generate" && processStatus?.status === "completed" && (
                  <p className="mt-2 text-slate-400 text-sm">Завершено. Можно закрыть окно прогресса и запустить новую.</p>
                )}
              </div>
              <p className="text-slate-500 text-xs">«Сгенерировать» — один дорвей по ключу в поле выше. «Сгенерировать пакет» — по каждому ключу из списка (поле выше кнопки). Галочки FAQ и Квиз действуют для одиночной и пакетной генерации.</p>
              <div className="flex items-center gap-4 flex-wrap">
                <label className="flex items-center gap-2 text-slate-300">
                  <input type="checkbox" checked={gen.save} onChange={(e) => setGen((g) => ({ ...g, save: e.target.checked }))} className="rounded" />
                  Сохранить в базу
                </label>
                <label className="flex items-center gap-2 text-slate-300">
                  <input type="checkbox" checked={gen.generate_faq} onChange={(e) => setGen((g) => ({ ...g, generate_faq: e.target.checked }))} className="rounded" />
                  Сгенерировать FAQ (3–5 вопросов)
                </label>
                <label className="flex items-center gap-2 text-slate-300">
                  <input type="checkbox" checked={gen.generate_quiz} onChange={(e) => setGen((g) => ({ ...g, generate_quiz: e.target.checked }))} className="rounded" />
                  Сгенерировать квиз (по теме оффера)
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
                {result.doorway_id ? ((result as { created_count?: number }).created_count && (result as { created_count?: number }).created_count! > 1 ? `Создано дорвеев: ${(result as { created_count?: number }).created_count}` : `Создан дорвей #${result.doorway_id}`) : "Превью"}
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
        <Select value={sortBy} onChange={(e) => { setSortBy((e.target.value || "") as "" | "health" | "revenue"); setPage(1); }} className="w-full sm:w-44">
          <option value="">Сортировка</option>
          <option value="health">По здоровью ↓</option>
          <option value="revenue">По выручке ↓</option>
        </Select>
      </div>

      {doorwaysMetrics?.external_signals_by_country && Object.keys(doorwaysMetrics.external_signals_by_country).length > 0 && (
        <div className="mb-4 p-4 rounded-xl bg-slate-800/80 border border-slate-600">
          <h3 className="text-sm font-medium text-violet-300 mb-2">Внешние данные по странам (гео офферов)</h3>
          <div className="flex flex-wrap gap-3">
            {Object.entries(doorwaysMetrics.external_signals_by_country).map(([country, sig]) => {
              const s = sig as { news?: { headlines?: unknown[] }; seasonality?: unknown; sources_used?: string[] };
              return (
                <div key={country} className="px-3 py-2 rounded-lg bg-slate-700/80 border border-slate-600 text-sm">
                  <span className="font-medium text-white uppercase">{country}</span>
                  {s.sources_used?.length ? (
                    <span className="text-slate-400 ml-2">источники: {s.sources_used.join(", ")}</span>
                  ) : null}
                  {s.news?.headlines?.length != null && s.news.headlines.length > 0 ? (
                    <span className="text-slate-400 ml-2">новости: {s.news.headlines.length}</span>
                  ) : null}
                  {s.seasonality != null && typeof s.seasonality === "object" && !("error" in s.seasonality) ? (
                    <span className="text-emerald-400 ml-2">сезонность</span>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}

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
          {(() => {
            const deployable = (paginated as Doorway[]).filter((d) => d.status !== "deployed" && d.status !== "indexed");
            const selectedCount = selectedDoorwayIds.size;
            const allDeployableSelected = deployable.length > 0 && deployable.every((d) => selectedDoorwayIds.has(d.id));
            const allInListSelected = paginated.length > 0 && (paginated as Doorway[]).every((d) => selectedDoorwayIds.has(d.id));
            const selectedDeployable = (paginated as Doorway[]).filter((d) => selectedDoorwayIds.has(d.id) && d.status !== "deployed" && d.status !== "indexed");
            return (
              <>
                <div className="flex flex-wrap items-center gap-3 px-4 py-2 border-b border-slate-700 bg-slate-800/50">
                  <label className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allDeployableSelected}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedDoorwayIds(new Set(deployable.map((d: Doorway) => d.id)));
                        else setSelectedDoorwayIds(new Set());
                      }}
                      className="rounded border-slate-600 text-emerald-600"
                    />
                    Выбрать все для деплоя ({deployable.length})
                  </label>
                  <label className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={allInListSelected}
                      onChange={(e) => {
                        if (e.target.checked) setSelectedDoorwayIds(new Set((paginated as Doorway[]).map((d) => d.id)));
                        else setSelectedDoorwayIds(new Set());
                      }}
                      className="rounded border-slate-600 text-amber-500"
                    />
                    Выбрать все в списке ({paginated.length})
                  </label>
                  <span className="flex items-center gap-2 text-slate-400 text-sm">
                    <label className="flex items-center gap-1.5">
                      <span>Выбрать для деплоя:</span>
                      <input
                        type="number"
                        min={1}
                        max={150}
                        value={selectForDeployN}
                        onChange={(e) => setSelectForDeployN(Math.max(1, Math.min(150, parseInt(e.target.value, 10) || 1)))}
                        className="w-14 px-1.5 py-1 bg-slate-700 border border-slate-600 rounded text-white text-sm"
                      />
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        const deployableFromFiltered = (filtered as Doorway[]).filter((d) => d.status !== "deployed" && d.status !== "indexed");
                        const firstN = deployableFromFiltered.slice(0, selectForDeployN).map((d) => d.id);
                        setSelectedDoorwayIds(new Set(firstN));
                        if (firstN.length > 0) toast.success(`Выбрано ${firstN.length} дорвеев для деплоя`);
                      }}
                      className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 text-white rounded-lg text-sm"
                    >
                      Применить
                    </button>
                  </span>
                  {selectedCount > 0 && selectedDeployable.length > 0 && (
                    <button
                      onClick={() => batchDeployMut.mutate(selectedDeployable.map((d) => d.id))}
                      disabled={batchDeployMut.isPending}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm"
                    >
                      {batchDeployMut.isPending ? "Отправка…" : `Деплой выбранных (${selectedDeployable.length})`}
                    </button>
                  )}
                  {batchDeployTaskIds.length > 0 && (
                    <button
                      onClick={() => setOpenProcess({ type: "deploy", task_id: batchDeployTaskIds[0] })}
                      className="px-4 py-2 bg-amber-600/80 hover:bg-amber-600 text-white rounded-lg text-sm"
                    >
                      Прогресс деплоя{batchDeployTaskIds.length > 1 ? ` (${batchDeployTaskIds.length})` : ""}
                    </button>
                  )}
                  {batchGenerateTaskIds.length > 0 && (
                    <button
                      onClick={() => setOpenProcess({ type: "generate", task_id: batchGenerateTaskIds[0] })}
                      className="px-4 py-2 bg-sky-600/80 hover:bg-sky-600 text-white rounded-lg text-sm"
                    >
                      Пакетная генерация{batchGenerateTaskIds.length > 1 ? ` (${batchGenerateTaskIds.length})` : ""}
                    </button>
                  )}
                  {batchDeleteTaskIds.length > 0 && (
                    <button
                      onClick={() => setOpenProcess({ type: "delete", task_id: batchDeleteTaskIds[0] })}
                      className="px-4 py-2 bg-red-600/80 hover:bg-red-600 text-white rounded-lg text-sm"
                    >
                      Прогресс удаления{batchDeleteTaskIds.length > 1 ? ` (${batchDeleteTaskIds.length})` : ""}
                    </button>
                  )}
                  {selectedCount > 0 && (
                    <button
                      onClick={() => batchQualityMut.mutate(Array.from(selectedDoorwayIds))}
                      disabled={batchQualityMut.isPending}
                      className="px-4 py-2 bg-violet-600/80 hover:bg-violet-600 disabled:opacity-50 text-white rounded-lg text-sm"
                    >
                      {batchQualityMut.isPending ? "Проверка…" : `Quality выбранных (${selectedCount})`}
                    </button>
                  )}
                  {selectedCount > 0 && (
                    <button
                      onClick={() => batchGenerateQuizMut.mutate(Array.from(selectedDoorwayIds))}
                      disabled={batchGenerateQuizMut.isPending}
                      className="px-4 py-2 bg-teal-600/80 hover:bg-teal-600 disabled:opacity-50 text-white rounded-lg text-sm"
                    >
                      {batchGenerateQuizMut.isPending ? "Генерация квизов…" : `Добавить квиз к выбранным (${selectedCount})`}
                    </button>
                  )}
                  {selectedCount > 0 && (
                    <button
                      onClick={() => {
                        const ids = Array.from(selectedDoorwayIds);
                        if (!ids.length) return;
                        if (!window.confirm(`Удалить выбранные дорвеи (${ids.length})?`)) return;
                        batchDeleteMut.mutate(ids);
                      }}
                      disabled={batchDeleteMut.isPending}
                      className="px-4 py-2 bg-red-600/80 hover:bg-red-600 disabled:opacity-50 text-white rounded-lg text-sm"
                    >
                      {batchDeleteMut.isPending ? "Запуск…" : `Удалить выбранные (${selectedCount})`}
                    </button>
                  )}
                  {batchDeleteTaskIds.length > 0 && (
                    <button
                      onClick={() => setOpenProcess({ type: "delete", task_id: batchDeleteTaskIds[0] })}
                      className="px-4 py-2 bg-red-600/80 hover:bg-red-600 text-white rounded-lg text-sm"
                    >
                      Прогресс удаления{batchDeleteTaskIds.length > 1 ? ` (${batchDeleteTaskIds.length})` : ""}
                    </button>
                  )}
                </div>
          <div className="overflow-x-auto overflow-y-auto max-h-[calc(100vh-320px)]">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="w-10 px-2 py-3"></th>
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
                  const canDeploy = d.status !== "deployed" && d.status !== "indexed";
                  return (
                    <tr
                      key={d.id}
                      className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-all duration-200 animate-fade-in-up"
                      style={{ animationDelay: `${Math.min(idx * 40, 200)}ms` }}
                    >
                      <td className="px-2 py-3">
                        <input
                          type="checkbox"
                          checked={selectedDoorwayIds.has(d.id)}
                          onChange={(e) => {
                            if (e.target.checked) setSelectedDoorwayIds((s) => new Set([...s, d.id]));
                            else setSelectedDoorwayIds((s) => { const n = new Set(s); n.delete(d.id); return n; });
                          }}
                          className="rounded border-slate-600 text-emerald-600"
                        />
                      </td>
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
                          {(() => {
                            const batchStatus = batchDeployStatusByDoorwayId.get(d.id);
                            const isDeployedByBatch = batchStatus === "success";
                            const isDeployingByBatch = batchStatus === "deploying";
                            const isErrorByBatch = batchStatus === "error";
                            const displayStatus = isDeployedByBatch ? "deployed" : isDeployingByBatch ? "deploying" : isErrorByBatch ? "error" : d.status;
                            const label = isDeployedByBatch ? "Задеплоен" : isDeployingByBatch ? "Деплой…" : isErrorByBatch ? "Ошибка" : (STATUS_LABELS[d.status] ?? d.status);
                            const statusClass = displayStatus === "deployed" ? "bg-emerald-500/20 text-emerald-400" : isDeployingByBatch ? "bg-amber-500/20 text-amber-400" : isErrorByBatch ? "bg-red-500/20 text-red-400" : d.status === "paused" ? "bg-amber-500/20 text-amber-400" : "bg-slate-600 text-slate-300";
                            return (
                              <>
                                <span className={`px-2 py-1 rounded text-xs font-medium inline-flex w-fit ${statusClass}`}>
                                  {label}
                                </span>
                                {d.status === "paused" && d.pause_reason && !batchStatus && (
                                  <span className="text-slate-500 text-xs max-w-[220px] truncate" title={d.pause_reason}>
                                    {d.pause_reason}
                                  </span>
                                )}
                              </>
                            );
                          })()}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {liveUrl && (batchDeployStatusByDoorwayId.get(d.id) === "success" || d.status === "deployed" || d.status === "indexed") && (
                            <a href={liveUrl} target="_blank" rel="noopener noreferrer" className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-emerald-400" title="Открыть">
                              <ExternalLink size={18} />
                            </a>
                          )}
                          <DropdownMenu
                            align="right"
                            trigger={<button className="p-1.5 rounded hover:bg-slate-700 text-slate-400 hover:text-white"><MoreVertical size={18} /></button>}
                          >
                            <DropdownMenuItem
                              onClick={() => {
                                api.get(`/deploy/doorway/${d.id}/preview`, { responseType: "text" })
                                  .then((res) => {
                                    const w = window.open("", "_blank");
                                    if (w) { w.document.write(res.data as string); w.document.close(); }
                                  })
                                  .catch((err: { response?: { data?: unknown; status?: number } }) => {
                                    let msg = "Не удалось загрузить предпросмотр";
                                    const d = err?.response?.data;
                                    if (err?.response?.status === 500 && d != null) {
                                      if (typeof d === "string") {
                                        try {
                                          const o = JSON.parse(d);
                                          if (typeof o?.detail === "string") msg = o.detail;
                                          else if (d.length < 200) msg = d;
                                        } catch {
                                          if (d.length < 200) msg = d;
                                        }
                                      } else if (typeof (d as { detail?: string })?.detail === "string") {
                                        msg = (d as { detail: string }).detail;
                                      }
                                    }
                                    toast.error(msg);
                                  });
                              }}
                            >
                              Предпросмотр
                            </DropdownMenuItem>
                            {canDeploy && (
                              <DropdownMenuItem onClick={() => setDeployDoorwayId(d.id)}>Деплой</DropdownMenuItem>
                            )}
                            {(d.status === "deployed" || d.status === "indexed") && (
                              <DropdownMenuItem onClick={() => setDeployDoorwayId(d.id)}>Повторный деплой</DropdownMenuItem>
                            )}
                            {(d.status === "deployed" || d.status === "indexed") && d.path !== "/" && (
                              <DropdownMenuItem onClick={() => fixRootMut.mutate(d.domain_id)} disabled={fixRootMut.isPending}>
                                {fixRootMut.isPending ? "…" : "Починить корень домена"}
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem onClick={() => runSslMut.mutate(d.id)} disabled={runSslMut.isPending}>
                              {runSslMut.isPending ? "SSL…" : "Получить SSL"}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setRecsDoorwayId(recsDoorwayId === d.id ? null : d.id)}>Рекомендации</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setVariantsDoorwayId(variantsDoorwayId === d.id ? null : d.id)}>
                              <Layers size={14} className="mr-2" /> Варианты A/B
                            </DropdownMenuItem>
                            {((d.cloaking_rules as { quiz?: { questions?: unknown[] } })?.quiz?.questions?.length ?? 0) > 0 && (
                              <DropdownMenuItem
                                onClick={() => quizToggleMut.mutate({ id: d.id, quiz_enabled: !(d.cloaking_rules as { quiz?: { enabled?: boolean } })?.quiz?.enabled })}
                                disabled={quizToggleMut.isPending}
                              >
                                Квиз: {(d.cloaking_rules as { quiz?: { enabled?: boolean } })?.quiz?.enabled ? "выкл" : "вкл"}
                              </DropdownMenuItem>
                            )}
                            {((d.cloaking_rules as { quiz?: { questions?: unknown[] } })?.quiz?.questions?.length ?? 0) === 0 && (
                              <DropdownMenuItem
                                onClick={() => generateQuizMut.mutate(d.id)}
                                disabled={generateQuizMut.isPending}
                              >
                                Добавить квиз
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuItem onClick={() => openPanel(d.id, "quality")}>Quality</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPanel(d.id, "predict")}>Predict CR</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPanel(d.id, "forecast")}>Прогноз прибыли</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPanel(d.id, "sources")}>Трафик по источникам</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => openPanel(d.id, "broken")}>Битые ссылки</DropdownMenuItem>
                            <DropdownMenuItem onClick={() => { setCloneDoorwayId(d.id); setCloneDomainId(domains?.[0]?.id ?? 0); setClonePath("/"); }}>
                              Клонировать на другой домен
                            </DropdownMenuItem>
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
          <div className="flex items-center justify-between px-4 py-2 border-t border-slate-700 text-slate-500 text-sm">
            <span>Всего: {filtered.length}</span>
          </div>
              </>
            );
          })()}
        </div>
      )}

      {cloneDoorwayId && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setCloneDoorwayId(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-md w-full mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-3">Клонировать дорвей #{cloneDoorwayId} на другой домен</h2>
            <p className="text-slate-400 text-sm mb-4">Создастся новый дорвей (черновик) с тем же контентом и настройками.</p>
            <div className="space-y-3">
              <div>
                <label className="block text-slate-400 text-sm mb-1">Домен</label>
                <select
                  value={cloneDomainId}
                  onChange={(e) => setCloneDomainId(Number(e.target.value))}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                >
                  {domains?.map((dom: { id: number; domain: string }) => (
                    <option key={dom.id} value={dom.id}>{dom.domain}</option>
                  ))}
                  {(!domains?.length) && <option value={0}>—</option>}
                </select>
              </div>
              <div>
                <label className="block text-slate-400 text-sm mb-1">Путь</label>
                <Input value={clonePath} onChange={(e) => setClonePath(e.target.value || "/")} placeholder="/" className="bg-slate-700 border-slate-600" />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button variant="outline" onClick={() => setCloneDoorwayId(null)}>Отмена</Button>
              <Button
                onClick={() => cloneDoorwayId && cloneToDomainMut.mutate({ id: cloneDoorwayId, domain_id: cloneDomainId, path: clonePath || "/" })}
                disabled={!cloneDomainId || cloneToDomainMut.isPending}
              >
                {cloneToDomainMut.isPending ? "Клонирование…" : "Клонировать"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {panelDoorwayId && panelType && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={closePanel}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-3 flex justify-between">
              <span>{panelType === "quality" ? "Quality Check" : panelType === "predict" ? "Predict CR" : panelType === "forecast" ? "Прогноз прибыли" : panelType === "sources" ? "Трафик по источникам" : "Битые ссылки"} — дорвей #{panelDoorwayId}</span>
              <button onClick={closePanel} className="text-slate-400 hover:text-white">✕</button>
            </h2>
            {panelType === "forecast" && (
              profitForecast ? (
                <div className="space-y-2 text-sm">
                  <p className={profitForecast.status === "profitable" ? "text-emerald-400" : profitForecast.status === "no_traffic" ? "text-slate-400" : "text-amber-400"}>
                    {profitForecast.message}
                  </p>
                  <p className="text-slate-400">Клики: {profitForecast.clicks}, конверсии: {profitForecast.conversions}, выручка: {profitForecast.revenue}</p>
                  {profitForecast.benchmark_roi != null && <p className="text-slate-400">Бенчмарк RPC: {profitForecast.benchmark_roi}</p>}
                  {profitForecast.days_to_profit != null && profitForecast.days_to_profit > 0 && (
                    <p className="text-amber-300">Выход в плюс ориентировочно через {profitForecast.days_to_profit} дн.</p>
                  )}
                </div>
              ) : <Skeleton className="h-24 w-full" />
            )}
            {panelType === "sources" && (
              trafficBySource ? (
                <div className="space-y-2 text-sm">
                  <p className="text-slate-400">За {trafficBySource.days} дн. (utm_source в ссылках клика)</p>
                  {trafficBySource.sources?.length ? (
                    <table className="w-full text-left">
                      <thead>
                        <tr className="border-b border-slate-600 text-slate-400">
                          <th className="py-1.5 font-medium">Источник</th>
                          <th className="py-1.5 font-medium">Клики</th>
                          <th className="py-1.5 font-medium">Конв.</th>
                          <th className="py-1.5 font-medium">Выручка</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(trafficBySource.sources as { source: string; clicks: number; conversions: number; revenue: number }[]).map((row, i) => (
                          <tr key={i} className="border-b border-slate-700/50 text-slate-300">
                            <td className="py-1.5 font-mono">{row.source || "—"}</td>
                            <td className="py-1.5">{row.clicks}</td>
                            <td className="py-1.5">{row.conversions}</td>
                            <td className="py-1.5">{row.revenue.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <p className="text-slate-500">Нет данных по источникам (добавьте utm_source в ссылки на клик)</p>}
                </div>
              ) : <Skeleton className="h-24 w-full" />
            )}
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
                {deployMut.isPending && (
                  <div className="p-3 bg-slate-700/50 rounded-lg border border-slate-600">
                    <p className="text-slate-300 text-sm">Деплой дорвея #{deployDoorwayId}</p>
                    <p className="text-slate-400 text-xs mt-1">Подключение к серверу, сборка HTML, отправка файлов…</p>
                    <div className="mt-2 h-1.5 bg-slate-600 rounded-full overflow-hidden">
                      <div className="h-full w-1/3 bg-emerald-500 rounded-full animate-pulse" style={{ animation: "pulse 1.5s ease-in-out infinite" }} />
                    </div>
                  </div>
                )}
                {deployMut.isSuccess && deployMut.data && (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
                    <p className="text-emerald-400 text-sm font-medium">✓ Деплой выполнен</p>
                    <p className="text-slate-300 text-xs mt-1 whitespace-pre-wrap">{(deployMut.data as { message?: string }).message ?? "Файлы загружены на сервер."}</p>
                    <Button className="mt-3" onClick={() => { setDeployDoorwayId(null); deployMut.reset(); }}>Закрыть</Button>
                  </div>
                )}
                {deployMut.isError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-red-400 text-sm font-medium">Ошибка деплоя</p>
                    <p className="text-slate-300 text-xs mt-1">{(deployMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Не удалось загрузить на сервер."}</p>
                    <div className="flex gap-2 mt-3">
                      <Button variant="secondary" onClick={() => { setDeployDoorwayId(null); deployMut.reset(); }}>Закрыть</Button>
                      <Button onClick={() => deployMut.mutate(deployDoorwayId)}>Повторить</Button>
                    </div>
                  </div>
                )}
                {!deployMut.isPending && !deployMut.isSuccess && !deployMut.isError && (
                  <>
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
                      <Button onClick={() => { setDeployDoorwayId(null); deployMut.reset(); }} variant="secondary">Отмена</Button>
                      <Button onClick={() => deployMut.mutate(deployDoorwayId)} disabled={deployMut.isPending}>
                        {deployMut.isPending ? "Деплой…" : "Деплоить"}
                      </Button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <p className="text-slate-400 text-sm">Загрузка проверки...</p>
            )}
          </div>
        </div>
      )}

      {openProcess && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => {
            const done = processStatus?.status === "completed" || processStatus?.status === "cancelled";
            if (done && openProcess.type === "deploy") { removeDeployTaskId(openProcess.task_id); qc.invalidateQueries({ queryKey: ["doorways"] }); }
            if (done && openProcess.type === "generate") { removeGenerateTaskId(openProcess.task_id); qc.invalidateQueries({ queryKey: ["doorways"] }); }
            if (done && openProcess.type === "delete") { removeDeleteTaskId(openProcess.task_id); qc.invalidateQueries({ queryKey: ["doorways"] }); setSelectedDoorwayIds(new Set()); }
            setOpenProcess(null);
          }}
        >
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-2xl w-full mx-4 max-h-[85vh] overflow-hidden flex flex-col shadow-xl" onClick={(e) => e.stopPropagation()}>
            {openProcess.type === "deploy" && (
              <>
                <h2 className="text-lg font-medium text-white mb-3 flex justify-between items-center">
                  <span>Пакетный деплой</span>
                  <button onClick={() => { if (processStatus?.status === "completed" || processStatus?.status === "cancelled") { removeDeployTaskId(openProcess.task_id); qc.invalidateQueries({ queryKey: ["doorways"] }); } setOpenProcess(null); }} className="text-slate-400 hover:text-white">✕</button>
                </h2>
                {processStatus ? (
                  <>
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-slate-400 mb-1">
                        <span>{processStatus.status === "queued" && "Подготовка…"} {processStatus.status === "running" && "В процессе…"} {processStatus.status === "paused" && "На паузе"} {processStatus.status === "completed" && "Завершён"} {processStatus.status === "cancelled" && "Отменён"}</span>
                        <span>{processStatus.current_index ?? 0} / {processStatus.total ?? 0}{processStatus.total ? ` (${Math.round(((processStatus.current_index ?? 0) / processStatus.total) * 100)}%)` : ""}</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 transition-all duration-300" style={{ width: `${processStatus.total ? Math.round(((processStatus.current_index ?? 0) / processStatus.total) * 100) : 0}%` }} />
                      </div>
                    </div>
                    <div className="overflow-y-auto flex-1 min-h-0 border border-slate-700 rounded-lg">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b border-slate-600 text-slate-400 text-left"><th className="py-2 px-2 font-medium w-24">Статус</th><th className="py-2 px-2 font-medium">Путь</th><th className="py-2 px-2 font-medium">Домен</th><th className="py-2 px-2 font-medium">Сообщение</th></tr></thead>
                        <tbody>
                          {(processStatus.results ?? []).map((r: { doorway_id: number; status: string; message?: string | null; path: string; domain: string }) => (
                            <tr key={r.doorway_id} className="border-b border-slate-700/50">
                              <td className="py-2 px-2 align-middle">
                                {r.status === "pending" && <span className="text-slate-500">В очереди</span>}
                                {r.status === "deploying" && (
                                  <span className="inline-flex flex-col gap-0.5">
                                    <span className="text-amber-400 text-xs">Деплой…</span>
                                    <div className="h-0.5 w-12 bg-slate-600 rounded overflow-hidden">
                                      <div className="h-full w-full bg-amber-500 rounded animate-pulse" style={{ width: "40%" }} />
                                    </div>
                                  </span>
                                )}
                                {r.status === "success" && <span className="text-emerald-400">✓</span>}
                                {r.status === "error" && <span className="text-red-400">Ошибка</span>}
                              </td>
                              <td className="py-2 px-2 text-slate-300 font-mono text-xs">{r.path || "—"}</td>
                              <td className="py-2 px-2 text-slate-400 text-xs truncate max-w-[120px]" title={r.domain}>{r.domain || "—"}</td>
                              <td className="py-2 px-2 text-slate-500 text-xs">{r.message ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {processStatus.error && <p className="text-red-400 text-sm mt-2">{processStatus.error}</p>}
                    <div className="pt-4 flex gap-2 flex-wrap">
                      {processStatus.status === "running" && (
                        <>
                          <Button variant="secondary" size="sm" onClick={async () => { await api.post(`/deploy/batch/${openProcess.task_id}/pause`); refetchProcessStatus(); }}>Пауза</Button>
                          <Button variant="destructive" size="sm" onClick={async () => { await api.post(`/deploy/batch/${openProcess.task_id}/cancel`); refetchProcessStatus(); }}>Отменить</Button>
                          <Button variant="ghost" size="sm" className="text-slate-400" onClick={async () => { try { await api.post(`/deploy/batch/${openProcess.task_id}/cancel`); } catch {} try { await api.post(`/deploy/batch/${openProcess.task_id}/dismiss`); } catch {} removeDeployTaskId(openProcess.task_id); setOpenProcess(null); }}>Убрать из списка</Button>
                        </>
                      )}
                      {processStatus.status === "paused" && (
                        <>
                          <Button size="sm" onClick={async () => { await api.post(`/deploy/batch/${openProcess.task_id}/resume`); refetchProcessStatus(); }}>Продолжить</Button>
                          <Button variant="destructive" size="sm" onClick={async () => { await api.post(`/deploy/batch/${openProcess.task_id}/cancel`); refetchProcessStatus(); }}>Отменить</Button>
                          <Button variant="ghost" size="sm" className="text-slate-400" onClick={async () => { try { await api.post(`/deploy/batch/${openProcess.task_id}/cancel`); } catch {} try { await api.post(`/deploy/batch/${openProcess.task_id}/dismiss`); } catch {} removeDeployTaskId(openProcess.task_id); setOpenProcess(null); }}>Убрать из списка</Button>
                        </>
                      )}
                      {(processStatus.status === "completed" || processStatus.status === "cancelled") && (
                        <Button variant="secondary" onClick={() => { removeDeployTaskId(openProcess.task_id); setOpenProcess(null); qc.invalidateQueries({ queryKey: ["doorways"] }); }}>Закрыть</Button>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    {processStatusError ? (
                      <div className="py-4">
                        <p className="text-amber-400 mb-2">Не удалось загрузить статус. Задача может ещё выполняться на сервере.</p>
                        <div className="flex gap-2 flex-wrap">
                          <Button variant="secondary" size="sm" onClick={() => refetchProcessStatus()}>Повторить</Button>
                          <Button variant="ghost" size="sm" className="text-slate-400" onClick={async () => { try { await api.post(`/deploy/batch/${openProcess.task_id}/cancel`); } catch {} try { await api.post(`/deploy/batch/${openProcess.task_id}/dismiss`); } catch {} removeDeployTaskId(openProcess.task_id); setOpenProcess(null); }}>Убрать из списка</Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-slate-400">Загрузка статуса…</p>
                    )}
                  </>
                )}
              </>
            )}

            {openProcess.type === "generate" && (
              <>
                <h2 className="text-lg font-medium text-white mb-3 flex justify-between items-center">
                  <span>Пакетная генерация</span>
                  <button onClick={() => { if (processStatus?.status === "completed") { removeGenerateTaskId(openProcess.task_id); qc.invalidateQueries({ queryKey: ["doorways"] }); } setOpenProcess(null); }} className="text-slate-400 hover:text-white">✕</button>
                </h2>
                {processStatus ? (
                  <>
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-slate-400 mb-1">
                        <span>{processStatus.status === "running" && "Генерация на сервере…"} {processStatus.status === "completed" && "Завершено"}</span>
                        <span>{processStatus.current_index ?? 0} / {processStatus.total ?? 0}{processStatus.total ? ` (${Math.round(((processStatus.current_index ?? 0) / processStatus.total) * 100)}%)` : ""}</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div className="h-full bg-sky-500 transition-all duration-300" style={{ width: `${processStatus.total ? Math.round(((processStatus.current_index ?? 0) / processStatus.total) * 100) : 0}%` }} />
                      </div>
                    </div>
                    <div className="overflow-y-auto flex-1 min-h-0 border border-slate-700 rounded-lg">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b border-slate-600 text-slate-400 text-left"><th className="py-2 px-2 font-medium w-24">Статус</th><th className="py-2 px-2 font-medium">Ключ</th><th className="py-2 px-2 font-medium w-16">Geo</th><th className="py-2 px-2 font-medium">Сообщение</th></tr></thead>
                        <tbody>
                          {(processStatus.results ?? []).map((r: { keyword: string; geo: string; status: string; error?: string; doorway_id?: number }, idx: number) => (
                            <tr key={idx} className="border-b border-slate-700/50">
                              <td className="py-2 px-2 align-middle">{r.status === "ok" && <span className="text-emerald-400">✓</span>} {r.status === "error" && <span className="text-red-400">Ошибка</span>}</td>
                              <td className="py-2 px-2 text-slate-300 text-xs">{r.keyword ?? "—"}</td>
                              <td className="py-2 px-2 text-slate-400 text-xs">{r.geo ?? "—"}</td>
                              <td className="py-2 px-2 text-slate-500 text-xs">{r.error ?? (r.doorway_id ? `#${r.doorway_id}` : "—")}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {processStatus.error && <p className="text-red-400 text-sm mt-2">{processStatus.error}</p>}
                    <div className="pt-4 flex gap-2">
                      {processStatus.status === "running" && (
                        <Button variant="ghost" size="sm" className="text-slate-400" onClick={async () => { try { await api.post(`/doorways/generate-batch/${openProcess.task_id}/dismiss`); } catch {} removeGenerateTaskId(openProcess.task_id); setOpenProcess(null); }}>Убрать из списка</Button>
                      )}
                      {processStatus.status === "completed" && (
                        <Button variant="secondary" onClick={() => { removeGenerateTaskId(openProcess.task_id); setOpenProcess(null); qc.invalidateQueries({ queryKey: ["doorways"] }); }}>Закрыть</Button>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    {processStatusError ? (
                      <div className="py-4">
                        <p className="text-amber-400 mb-2">Не удалось загрузить статус.</p>
                        <div className="flex gap-2 flex-wrap">
                          <Button variant="secondary" size="sm" onClick={() => refetchProcessStatus()}>Повторить</Button>
                          <Button variant="ghost" size="sm" className="text-slate-400" onClick={async () => { try { await api.post(`/doorways/generate-batch/${openProcess.task_id}/dismiss`); } catch {} removeGenerateTaskId(openProcess.task_id); setOpenProcess(null); }}>Убрать из списка</Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-slate-400">Загрузка статуса…</p>
                    )}
                  </>
                )}
              </>
            )}

            {openProcess.type === "delete" && (
              <>
                <h2 className="text-lg font-medium text-white mb-3 flex justify-between items-center">
                  <span>Удаление дорвеев</span>
                  <button onClick={() => { if (processStatus?.status === "completed" || processStatus?.status === "cancelled") { removeDeleteTaskId(openProcess.task_id); qc.invalidateQueries({ queryKey: ["doorways"] }); setSelectedDoorwayIds(new Set()); } setOpenProcess(null); }} className="text-slate-400 hover:text-white">✕</button>
                </h2>
                {processStatus ? (
                  <>
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-slate-400 mb-1">
                        <span>{processStatus.status === "running" && "Удаление с сервера и из базы…"} {processStatus.status === "completed" && "Завершено"}</span>
                        <span>{processStatus.current_index ?? 0} / {processStatus.total ?? 0}{processStatus.total ? ` (${Math.round(((processStatus.current_index ?? 0) / processStatus.total) * 100)}%)` : ""}</span>
                      </div>
                      <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                        <div className={`h-full bg-red-500 transition-all duration-300 ${processStatus.status === "running" ? "animate-pulse" : ""}`} style={{ width: `${processStatus.total ? Math.round(((processStatus.current_index ?? 0) / processStatus.total) * 100) : 0}%` }} />
                      </div>
                    </div>
                    <div className="overflow-y-auto flex-1 min-h-0 border border-slate-700 rounded-lg">
                      <table className="w-full text-sm">
                        <thead><tr className="border-b border-slate-600 text-slate-400 text-left"><th className="py-2 px-2 font-medium w-24">Статус</th><th className="py-2 px-2 font-medium">Путь</th><th className="py-2 px-2 font-medium">Домен</th><th className="py-2 px-2 font-medium">Сообщение</th></tr></thead>
                        <tbody>
                          {(processStatus.results ?? []).map((r: { doorway_id: number; path: string; domain: string; status: string; message?: string | null }, idx: number) => (
                            <tr key={idx} className="border-b border-slate-700/50">
                              <td className="py-2 px-2 align-middle">{r.status === "removed" && <span className="text-emerald-400">✓ Удалён</span>} {r.status === "pending" && <span className="text-amber-400 text-xs">В очереди</span>} {r.status === "error" && <span className="text-red-400">Ошибка</span>}</td>
                              <td className="py-2 px-2 text-slate-300 font-mono text-xs">{r.path ?? "—"}</td>
                              <td className="py-2 px-2 text-slate-400 text-xs truncate max-w-[120px]" title={r.domain}>{r.domain ?? "—"}</td>
                              <td className="py-2 px-2 text-slate-500 text-xs">{r.message ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {processStatus.error && <p className="text-red-400 text-sm mt-2">{processStatus.error}</p>}
                    <div className="pt-4 flex gap-2">
                      {processStatus.status === "running" && (
                        <Button variant="ghost" size="sm" className="text-slate-400" onClick={async () => { try { await api.post(`/doorways/batch-delete/${openProcess.task_id}/dismiss`); } catch {} removeDeleteTaskId(openProcess.task_id); setOpenProcess(null); setSelectedDoorwayIds(new Set()); }}>Убрать из списка</Button>
                      )}
                      {processStatus.status === "completed" && (
                        <Button variant="secondary" onClick={() => { removeDeleteTaskId(openProcess.task_id); setOpenProcess(null); qc.invalidateQueries({ queryKey: ["doorways"] }); setSelectedDoorwayIds(new Set()); }}>Закрыть</Button>
                      )}
                    </div>
                  </>
                ) : (
                  <>
                    {processStatusError ? (
                      <div className="py-4">
                        <p className="text-amber-400 mb-2">Не удалось загрузить статус.</p>
                        <div className="flex gap-2 flex-wrap">
                          <Button variant="secondary" size="sm" onClick={() => refetchProcessStatus()}>Повторить</Button>
                          <Button variant="ghost" size="sm" className="text-slate-400" onClick={async () => { try { await api.post(`/doorways/batch-delete/${openProcess.task_id}/dismiss`); } catch {} removeDeleteTaskId(openProcess.task_id); setOpenProcess(null); setSelectedDoorwayIds(new Set()); }}>Убрать из списка</Button>
                        </div>
                      </div>
                    ) : (
                      <p className="text-slate-400">Загрузка статуса…</p>
                    )}
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {batchQualityResults !== null && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setBatchQualityResults(null)}>
          <div className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-4xl w-full mx-4 max-h-[85vh] overflow-hidden flex flex-col shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-medium text-white mb-3 flex justify-between">
              <span>Quality — результаты проверки ({batchQualityResults.length})</span>
              <button onClick={() => setBatchQualityResults(null)} className="text-slate-400 hover:text-white">✕</button>
            </h2>
            {qualityUniqueFixCodes.length > 0 && (
              <div className="mb-3 p-3 bg-slate-700/50 rounded-lg border border-slate-600">
                <p className="text-slate-400 text-xs font-medium mb-2">Применить исправления</p>
                <div className="flex flex-wrap gap-3 items-center">
                  {qualityUniqueFixCodes.map((code) => (
                    <label key={code} className="flex items-center gap-2 text-slate-300 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={qualityApplyFixCodes.has(code)}
                        onChange={(e) => {
                          if (e.target.checked) setQualityApplyFixCodes((s) => new Set([...s, code]));
                          else setQualityApplyFixCodes((s) => { const n = new Set(s); n.delete(code); return n; });
                        }}
                        className="rounded border-slate-600 text-emerald-600"
                      />
                      {FIX_CODE_LABELS[code] ?? code}
                    </label>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2 mt-2">
                  <Button
                    size="sm"
                    disabled={qualityApplyFixCodes.size === 0 || qualityApplySelectedIds.size === 0 || batchApplyWarningsMut.isPending}
                    onClick={() => batchApplyWarningsMut.mutate({ doorway_ids: Array.from(qualityApplySelectedIds), fix_codes: Array.from(qualityApplyFixCodes) })}
                  >
                    {batchApplyWarningsMut.isPending ? "Применяю…" : `Применить к выбранным (${qualityApplySelectedIds.size})`}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={qualityApplyFixCodes.size === 0 || batchApplyWarningsMut.isPending}
                    onClick={() => batchApplyWarningsMut.mutate({ doorway_ids: batchQualityResults.map((r) => r.doorway_id), fix_codes: Array.from(qualityApplyFixCodes) })}
                  >
                    {batchApplyWarningsMut.isPending ? "Применяю…" : `Применить ко всем (${batchQualityResults.length})`}
                  </Button>
                </div>
              </div>
            )}
            {batchQualityResults.length > 0 && (
              <p className="text-slate-500 text-xs mb-2">
                Рекомендации AI по дорвеям: в меню Действия → Рекомендации для каждого дорвея. Или выберите строки и откройте рекомендации для первого выбранного:
                <Button
                  size="sm"
                  variant="secondary"
                  className="ml-2"
                  onClick={() => {
                    const id = qualityApplySelectedIds.size > 0
                      ? Array.from(qualityApplySelectedIds)[0]
                      : batchQualityResults[0].doorway_id;
                    setRecsDoorwayId(id);
                    setBatchQualityResults(null);
                  }}
                >
                  Открыть рекомендации
                </Button>
              </p>
            )}
            <div className="overflow-y-auto flex-1 min-h-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-600 text-slate-400">
                    <th className="w-10 py-2 pr-1 text-left font-medium">
                      <input
                        type="checkbox"
                        checked={batchQualityResults.length > 0 && qualityApplySelectedIds.size === batchQualityResults.length}
                        onChange={(e) => {
                          if (e.target.checked) setQualityApplySelectedIds(new Set(batchQualityResults.map((r) => r.doorway_id)));
                          else setQualityApplySelectedIds(new Set());
                        }}
                        className="rounded border-slate-600 text-emerald-600"
                      />
                    </th>
                    <th className="text-left py-2 font-medium">ID</th>
                    <th className="text-left py-2 font-medium">Путь</th>
                    <th className="text-left py-2 font-medium">Заголовок</th>
                    <th className="text-left py-2 font-medium w-20">OK</th>
                    <th className="text-left py-2 font-medium">Ошибки / предупреждения</th>
                  </tr>
                </thead>
                <tbody>
                  {batchQualityResults.map((row) => (
                    <tr key={row.doorway_id} className="border-b border-slate-700/50">
                      <td className="py-2 pr-1">
                        <input
                          type="checkbox"
                          checked={qualityApplySelectedIds.has(row.doorway_id)}
                          onChange={(e) => {
                            if (e.target.checked) setQualityApplySelectedIds((s) => new Set([...s, row.doorway_id]));
                            else setQualityApplySelectedIds((s) => { const n = new Set(s); n.delete(row.doorway_id); return n; });
                          }}
                          className="rounded border-slate-600 text-emerald-600"
                        />
                      </td>
                      <td className="py-2 font-mono text-white">{row.doorway_id}</td>
                      <td className="py-2 text-slate-300">{row.path || "—"}</td>
                      <td className="py-2 text-slate-400 truncate max-w-[180px]" title={row.title}>{row.title || "—"}</td>
                      <td className="py-2">{row.ok ? <span className="text-emerald-400">✓</span> : <span className="text-amber-400">⚠</span>}</td>
                      <td className="py-2">
                        {row.errors?.length ? <div className="text-red-400 text-xs">{row.errors.join("; ")}</div> : null}
                        {row.warnings?.length ? <div className="text-amber-400 text-xs mt-0.5">{row.warnings.join("; ")}</div> : null}
                        {!row.errors?.length && !row.warnings?.length ? <span className="text-slate-500">—</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pt-3 border-t border-slate-700 flex justify-between items-center">
              <span className="text-slate-500 text-sm">Выбрано: {qualityApplySelectedIds.size} из {batchQualityResults.length}</span>
              <Button variant="secondary" onClick={() => setBatchQualityResults(null)}>Закрыть</Button>
            </div>
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
            <p className="text-slate-500 text-xs mb-3">«Применить» — AI сгенерирует улучшенные title, meta и контент по рекомендации и подставит в дорвей (предыдущая версия сохраняется для Rollback).</p>
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
