import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../api/client";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { FileCode, Plus, Pencil, Trash2 } from "lucide-react";

type Template = {
  id: number;
  name: string;
  type: string;
  content: string | null;
  variables: string[] | null;
  created_at: string;
  updated_at: string;
};

const TEMPLATE_VARS_HINT = "title, meta_description, main_content, language, affiliate_url, canonical_url, body_class, faq_schema, article_schema, exit_intent_enabled, exit_intent_title, exit_intent_cta, data_offers, doorway_id";

export default function Templates() {
  const qc = useQueryClient();
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState({ name: "", type: "page", content: "", variables: "" });

  const { data: templates, isLoading } = useQuery({
    queryKey: ["templates"],
    queryFn: () => api.get("/templates/").then((r) => r.data),
  });

  const createMut = useMutation({
    mutationFn: (d: { name: string; type: string; content: string; variables?: string[] }) =>
      api.post("/templates/", { ...d, variables: d.variables?.length ? d.variables : undefined }).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates"] });
      setModal(null);
      resetForm();
    },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { name?: string; type?: string; content?: string; variables?: string[] } }) =>
      api.patch(`/templates/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates"] });
      setModal(null);
      setEditId(null);
      resetForm();
    },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.delete(`/templates/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates"] }),
  });

  function resetForm() {
    setForm({ name: "", type: "page", content: "", variables: "" });
  }

  function variablesFromStr(s: string): string[] {
    return s
      .split(/[,\n]/)
      .map((x) => x.trim())
      .filter(Boolean);
  }

  const openCreate = () => {
    setEditId(null);
    setForm({ name: "", type: "page", content: "", variables: "" });
    setModal("create");
  };

  const openEdit = (t: Template) => {
    setEditId(t.id);
    setForm({
      name: t.name,
      type: t.type || "page",
      content: t.content ?? "",
      variables: Array.isArray(t.variables) ? t.variables.join(", ") : "",
    });
    setModal("edit");
  };

  const saveCreate = () => {
    createMut.mutate({
      name: form.name,
      type: form.type,
      content: form.content,
      variables: variablesFromStr(form.variables),
    });
  };

  const saveEdit = () => {
    if (editId == null) return;
    updateMut.mutate({
      id: editId,
      data: {
        name: form.name,
        type: form.type,
        content: form.content,
        variables: variablesFromStr(form.variables),
      },
    });
  };

  const isFormValid = form.name.trim().length > 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Шаблоны</h1>
        <Button onClick={openCreate}>
          <Plus className="w-4 h-4 mr-2" />
          Создать шаблон
        </Button>
      </div>

      <p className="text-slate-400 text-sm mb-4">
        Шаблоны страниц (Jinja2). Переменные: {TEMPLATE_VARS_HINT}
      </p>

      {isLoading ? (
        <p className="text-slate-400">Загрузка...</p>
      ) : (
        <div className="bg-slate-800/80 rounded-xl border border-slate-700 overflow-hidden">
          {templates?.length ? (
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-700">
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">ID</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Название</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Тип</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Размер</th>
                  <th className="text-left px-4 py-3 text-slate-400 font-medium">Действия</th>
                </tr>
              </thead>
              <tbody>
                {(templates as Template[]).map((t) => (
                  <tr key={t.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-white">{t.id}</td>
                    <td className="px-4 py-3 text-white">{t.name}</td>
                    <td className="px-4 py-3 text-slate-400">{t.type}</td>
                    <td className="px-4 py-3 text-slate-500 text-sm">
                      {(t.content?.length ?? 0) > 0 ? `${(t.content?.length ?? 0).toLocaleString()} симв.` : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => openEdit(t)}
                        className="text-emerald-400 hover:underline text-sm inline-flex items-center gap-1 mr-2"
                      >
                        <Pencil className="w-3.5 h-3.5" /> Изменить
                      </button>
                      <button
                        onClick={() => window.confirm("Удалить шаблон?") && deleteMut.mutate(t.id)}
                        disabled={deleteMut.isPending}
                        className="text-red-400 hover:underline text-sm inline-flex items-center gap-1"
                      >
                        <Trash2 className="w-3.5 h-3.5" /> Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center">
              <div className="rounded-full bg-slate-700/50 w-16 h-16 flex items-center justify-center mx-auto mb-4">
                <FileCode className="text-slate-500" size={32} strokeWidth={1.5} />
              </div>
              <p className="text-slate-400">Пока нет шаблонов</p>
              <p className="text-slate-500 text-sm mt-1">Создайте шаблон для кастомизации страниц дорвеев</p>
              <Button className="mt-4" onClick={openCreate}>
                <Plus className="w-4 h-4 mr-2" /> Создать шаблон
              </Button>
            </div>
          )}
        </div>
      )}

      {modal && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 overflow-y-auto py-8"
          onClick={() => {
            setModal(null);
            setEditId(null);
          }}
        >
          <div
            className="bg-slate-800 rounded-xl border border-slate-600 p-6 max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-medium text-white mb-4">
              {modal === "create" ? "Новый шаблон" : "Редактировать шаблон"}
            </h2>

            <div className="space-y-4">
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Название</label>
                  <Input
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Страница по умолчанию"
                    className="bg-slate-700 border-slate-600"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Тип</label>
                  <select
                    value={form.type}
                    onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                  >
                    <option value="page">page — полная страница</option>
                    <option value="block">block — фрагмент</option>
                    <option value="style">style — стили</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Тело шаблона (HTML + Jinja2)</label>
                  <textarea
                    value={form.content}
                    onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
                    placeholder="<!DOCTYPE html>..."
                    rows={14}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white font-mono text-sm placeholder-slate-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 text-sm mb-1">Переменные (через запятую, опционально)</label>
                  <Input
                    value={form.variables}
                    onChange={(e) => setForm((f) => ({ ...f, variables: e.target.value }))}
                    placeholder={TEMPLATE_VARS_HINT}
                    className="bg-slate-700 border-slate-600"
                  />
                </div>
              </div>

            <div className="flex justify-end gap-2 mt-6">
              <Button variant="secondary" onClick={() => { setModal(null); setEditId(null); }}>
                Отмена
              </Button>
              <Button
                onClick={modal === "create" ? saveCreate : saveEdit}
                disabled={!isFormValid || createMut.isPending || updateMut.isPending}
              >
                {createMut.isPending || updateMut.isPending ? "Сохранение..." : "Сохранить"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
