import { useEffect, useId, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import mermaid from "mermaid";
import api from "../api/client";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  securityLevel: "loose",
});

export default function Instruction() {
  const containerRef = useRef<HTMLDivElement>(null);
  const baseId = useId().replace(/:/g, "-");

  const { data: content, isLoading, error } = useQuery({
    queryKey: ["instruction"],
    queryFn: async () => {
      const r = await api.get("/docs/instruction", { responseType: "text" });
      return r.data as string;
    },
  });

  useEffect(() => {
    if (!content || !containerRef.current) return;
    const els = containerRef.current.querySelectorAll<HTMLDivElement>(".mermaid-source");
    if (els.length === 0) return;
    const run = async () => {
      for (let i = 0; i < els.length; i++) {
        const el = els[i];
        const target = el.nextElementSibling as HTMLDivElement | null;
        const src = el.textContent?.trim();
        if (!target || !src) continue;
        try {
          const id = `mermaid-${baseId}-${i}`;
          const { svg } = await mermaid.render(id, src);
          target.innerHTML = svg;
          target.classList.remove("hidden");
        } catch {
          target.innerHTML = '<span class="text-amber-400 text-sm">Ошибка отрисовки диаграммы</span>';
          target.classList.remove("hidden");
        }
      }
    };
    run();
  }, [content, baseId]);

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
    <div ref={containerRef} className="max-w-4xl">
      <article className="prose prose-invert prose-slate max-w-none prose-headings:text-white prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-white prose-code:bg-slate-700 prose-code:px-1 prose-code:rounded prose-pre:bg-slate-800 prose-pre:border prose-pre:border-slate-600">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ src, alt }) => (
              <img src={src} alt={alt ?? ""} className="rounded-lg border border-slate-600 max-w-full h-auto" loading="lazy" />
            ),
            pre: ({ node, children, ...props }) => {
              const codeEl = Array.isArray(children) ? children[0] : children;
              const code = codeEl && typeof codeEl === "object" && "props" in codeEl ? codeEl : null;
              const isMermaid = code?.props?.className?.includes?.("language-mermaid");
              const text = typeof code?.props?.children === "string" ? code.props.children : "";
              if (isMermaid && text) {
                return (
                  <div className="my-6">
                    <div className="mermaid-source hidden" aria-hidden="true">{text}</div>
                    <div className="mermaid-output min-h-[120px] flex items-center justify-center overflow-x-auto rounded-lg border border-slate-600 bg-slate-800/50 hidden [&>svg]:max-w-full [&>svg]:h-auto" />
                  </div>
                );
              }
              return <pre {...props}>{children}</pre>;
            },
          }}
        >
          {content}
        </ReactMarkdown>
      </article>
    </div>
  );
}
