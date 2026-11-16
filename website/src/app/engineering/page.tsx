import type { Metadata } from "next";
import { ComingSoonPanel } from "@/components/ComingSoonPanel";
import { PageHero } from "@/components/PageHero";

export const metadata: Metadata = {
  title: "Engineering",
  description:
    "Engineering evidence and design decisions for QwenNews. W0 reserves the page; measured results will be published only from verified sources.",
};

const principles = [
  {
    title: "No invented numbers",
    body: "Benchmarks, latency figures, and rankings appear only when measured and cited from repository evaluation artifacts.",
  },
  {
    title: "Honest product claims",
    body: "The project uses a pretrained Qwen3 4B model through Ollama. It does not claim custom training or fine-tuning.",
  },
  {
    title: "Evidence over polish",
    body: "Design decisions should show tradeoffs — ranking weights, concurrency limits, watermark safety — not marketing copy.",
  },
] as const;

export default function EngineeringPage() {
  return (
    <div className="shell space-y-10 pb-20">
      <PageHero
        eyebrow="Engineering"
        title="Benchmarks and design decisions"
        description="This page will host measured evidence and the rationale behind ranking, caching, orchestration, and reliability choices."
      />

      <div className="grid gap-4 md:grid-cols-3">
        {principles.map((item) => (
          <article
            key={item.title}
            className="rounded-2xl border border-line/80 bg-ink-elevated/55 p-5"
          >
            <h2 className="text-xl">{item.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">{item.body}</p>
          </article>
        ))}
      </div>

      <ComingSoonPanel
        milestone="W3"
        title="Evidence panels reserved"
        summary="No benchmark tables or charts are published in W0. Empty states stay explicit until real evaluation outputs are selected for the public site."
        planned={[
          "Analysis quality rubric excerpts",
          "Latency and throughput measurements (when available)",
          "Ranking and diversity design notes",
          "Reliability / orchestration outcome glossary",
        ]}
      />
    </div>
  );
}
