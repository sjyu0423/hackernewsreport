import type { Metadata } from "next";
import Link from "next/link";
import { PageHero } from "@/components/PageHero";
import { engineeringEvidence, evidenceConditions } from "@/lib/evidence";

export const metadata: Metadata = {
  title: "Engineering",
  description:
    "Verified engineering evidence for QwenNews: local Qwen3 4B throughput, M1 benchmark wall time, source count, and test suite size.",
};

export default function EngineeringPage() {
  return (
    <div className="shell space-y-10 pb-20">
      <PageHero
        eyebrow="Engineering"
        title="Benchmarks and design decisions"
        description="Only repository-verified measurements appear here. No invented latency charts or live counters."
      />

      <dl className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {engineeringEvidence.map((item) => (
          <div
            key={item.label}
            className="rounded-2xl border border-line/80 bg-ink-elevated/55 p-5"
          >
            <dt className="font-mono text-xs uppercase tracking-[0.14em] text-violet">
              {item.label}
            </dt>
            <dd className="mt-2 font-display text-2xl text-paper">
              {item.value}
            </dd>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              {item.detail}
            </p>
          </div>
        ))}
      </dl>

      <section className="panel space-y-4 p-6 sm:p-8">
        <h2 className="text-2xl sm:text-3xl">Benchmark conditions</h2>
        <ul className="space-y-2 text-sm leading-relaxed text-muted">
          {evidenceConditions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <p className="text-sm text-muted">
          Primary sources:{" "}
          <code className="font-mono text-paper/85">docs/milestones/m1.md</code>
          ,{" "}
          <code className="font-mono text-paper/85">
            data/reports/live_m1_benchmark.json
          </code>
          , and local{" "}
          <code className="font-mono text-paper/85">pytest --collect-only</code>.
        </p>
        <Link href="/demo/" className="btn-secondary inline-flex no-underline">
          See analyses in the demo
        </Link>
      </section>
    </div>
  );
}
