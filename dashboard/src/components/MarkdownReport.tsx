"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import { safeHref } from "@/lib/format";

/** Sanitize schema: no raw HTML; links limited further in components. */
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: (defaultSchema.tagNames || []).filter(
    (tag) => !["script", "iframe", "object", "embed", "form", "input", "style"].includes(tag),
  ),
  attributes: {
    ...defaultSchema.attributes,
    a: ["href", "title", "rel", "target"],
    code: ["className"],
  },
};

type Props = {
  markdown: string;
  emptyLabel?: string;
};

export function MarkdownReport({
  markdown,
  emptyLabel = "This report has no Markdown body stored.",
}: Props) {
  const text = (markdown || "").trim();
  if (!text) {
    return <p className="empty">{emptyLabel}</p>;
  }

  return (
    <div className="markdown-body" data-testid="markdown-report">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
        components={{
          a: ({ href, children }) => {
            const safe = safeHref(href ?? null);
            if (!safe) {
              return <span className="unsafe-link">{children}</span>;
            }
            return (
              <a href={safe} rel="noopener noreferrer" target="_blank">
                {children}
              </a>
            );
          },
          img: () => null,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
