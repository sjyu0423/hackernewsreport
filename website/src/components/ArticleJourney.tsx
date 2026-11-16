import Link from "next/link";
import { buildArticleJourney } from "@/lib/architecture";
import { safeSourceHref } from "@/lib/demo";
import { formatUtcDate } from "@/lib/format";

export function ArticleJourney() {
  const journey = buildArticleJourney();
  const { story } = journey;
  const href = safeSourceHref(story.source_url);

  return (
    <section className="space-y-6" aria-labelledby="article-journey-heading">
      <div className="max-w-3xl">
        <h2 id="article-journey-heading" className="text-3xl sm:text-4xl">
          One article’s journey
        </h2>
        <p className="mt-3 text-muted">
          Walkthrough for{" "}
          <span className="text-paper">{story.headline}</span> using the curated
          W1 snapshot. Actual analysis text comes from local Qwen3 4B; schematic
          steps are labeled when they illustrate structure rather than exported
          DB rows.
        </p>
      </div>

      <div className="panel space-y-4 p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-3">
          <span className="status-chip">
            <span className="status-dot" aria-hidden="true" />
            Snapshot {journey.snapshotId}
          </span>
          <span className="text-xs text-muted">
            Recorded {formatUtcDate(journey.recordedAt)}
          </span>
        </div>
        <div className="flex flex-wrap gap-3 text-sm text-muted">
          <span>{story.source_name}</span>
          <span aria-hidden="true">·</span>
          <span>{story.category}</span>
          <span aria-hidden="true">·</span>
          <span>{story.id}</span>
        </div>
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex text-sm"
          >
            Open original source
          </a>
        ) : null}
      </div>

      <ol className="space-y-4">
        {journey.steps.map((step) => (
          <li key={step.id} className="panel p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-3">
              <h3 className="text-xl sm:text-2xl">{step.title}</h3>
              <span
                className={`rounded-full border px-2.5 py-1 font-mono text-[0.65rem] uppercase tracking-[0.12em] ${
                  step.kind === "actual"
                    ? "border-ok/40 text-ok"
                    : "border-warn/40 text-warn"
                }`}
              >
                {step.kind === "actual" ? "Actual snapshot data" : "Schematic"}
              </span>
            </div>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
              {step.body}
            </p>
            <dl className="mt-5 grid gap-3 sm:grid-cols-2">
              {step.facts.map((fact) => (
                <div
                  key={`${step.id}-${fact.label}`}
                  className="rounded-xl border border-line/70 bg-ink-soft/35 p-3"
                >
                  <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-muted">
                    {fact.label}
                  </dt>
                  <dd className="mt-1 text-sm leading-relaxed text-paper/90">
                    {fact.value}
                  </dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ol>

      <p className="text-sm text-muted">
        Explore the same analysis in the{" "}
        <Link href="/demo/" className="no-underline">
          interactive demo
        </Link>
        .
      </p>
    </section>
  );
}
