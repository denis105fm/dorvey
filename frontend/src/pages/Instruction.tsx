import { useEffect, useId, useRef, useState } from "react";
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

function slugify(text: string): string {
  return String(text)
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/\./g, "")
    .replace(/[^\p{L}\p{N}-]/gu, "")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

export default function Instruction() {
  const containerRef = useRef<HTMLDivElement>(null);
  const baseId = useId().replace(/:/g, "-");
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);

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

  const handleAnchorClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    const href = (e.currentTarget as HTMLAnchorElement).getAttribute("href");
    if (href?.startsWith("#") && href.length > 1) {
      const id = href.slice(1);
      const el = document.getElementById(id);
      if (el) {
        e.preventDefault();
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  };

  const getHeadingText = (node: unknown, children: React.ReactNode): string => {
    const n = node as { children?: Array<{ value?: string }> } | undefined;
    const fromNode = n?.children?.map((c) => c.value ?? "").join("").trim();
    if (fromNode) return fromNode;
    const extract = (c: React.ReactNode): string =>
      typeof c === "string" ? c : Array.isArray(c) ? c.map(extract).join("") : "";
    return extract(children).trim();
  };

  const heading = (Tag: "h1" | "h2" | "h3" | "h4") =>
    ({ node, children, ...props }: React.ComponentProps<"h1"> & { node?: unknown }) => {
      const text = getHeadingText(node, children);
      const id = slugify(text);
      return id ? <Tag id={id} {...props}>{children}</Tag> : <Tag {...props}>{children}</Tag>;
    };

  return (
    <div ref={containerRef} className="max-w-4xl scroll-smooth relative">
      <article className="prose prose-invert prose-slate max-w-none prose-headings:text-white prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-white prose-code:bg-slate-700 prose-code:px-1 prose-code:rounded prose-pre:bg-slate-800 prose-pre:border prose-pre:border-slate-600">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: heading("h1"),
            h2: heading("h2"),
            h3: heading("h3"),
            h4: heading("h4"),
            a: ({ href, children, ...props }) => (
              <a href={href} onClick={handleAnchorClick} {...props}>{children}</a>
            ),
            img: ({ src, alt }) => (
              <button
                type="button"
                onClick={() => src && setLightboxSrc(src)}
                className="block w-full text-left cursor-zoom-in"
              >
                <img src={src} alt={alt ?? ""} className="rounded-lg border border-slate-600 max-w-full h-auto hover:border-emerald-500/50 transition-colors" loading="lazy" />
              </button>
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

      {lightboxSrc && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 cursor-zoom-out"
          onClick={() => setLightboxSrc(null)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Escape" && setLightboxSrc(null)}
          aria-label="Закрыть"
        >
          <img
            src={lightboxSrc}
            alt=""
            className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
