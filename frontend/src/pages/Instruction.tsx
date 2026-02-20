import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import api from "../api/client";

export default function Instruction() {
  const { data: content, isLoading, error } = useQuery({
    queryKey: ["instruction"],
    queryFn: async () => {
      const r = await api.get("/docs/instruction", { responseType: "text" });
      return r.data as string;
    },
  });

  if (isLoading) {
    return (
      <div className="text-slate-400">Загрузка инструкции…</div>
    );
  }
  if (error || !content) {
    return (
      <div className="text-amber-400">
        Не удалось загрузить инструкцию. Проверьте, что файл docs/ИНСТРУКЦИЯ.md доступен на сервере.
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      <article className="prose prose-invert prose-slate max-w-none prose-headings:text-white prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-white prose-code:bg-slate-700 prose-code:px-1 prose-code:rounded prose-pre:bg-slate-800 prose-pre:border prose-pre:border-slate-600">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ src, alt }) => (
              <img src={src} alt={alt ?? ""} className="rounded-lg border border-slate-600 max-w-full h-auto" />
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </article>
    </div>
  );
}
