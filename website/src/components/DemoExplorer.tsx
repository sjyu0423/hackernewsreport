"use client";

import { useMemo, useState } from "react";
import {
  type DemoSort,
  type DemoStory,
  filterAndSortStories,
  listCategories,
  safeSourceHref,
} from "@/lib/demo";
import { formatUtcDate, scoreLabel } from "@/lib/format";

type DemoExplorerProps = {
  stories: DemoStory[];
  snapshotId: string;
  recordedAt: string;
  disclaimer: string;
  modelId: string;
  quantization: string;
};

export function DemoExplorer({
  stories,
  snapshotId,
  recordedAt,
  disclaimer,
  modelId,
  quantization,
}: DemoExplorerProps) {
  const categories = useMemo(() => listCategories(stories), [stories]);
  const [category, setCategory] = useState<string>("all");
  const [sort, setSort] = useState<DemoSort>("significance");
  const [expanded, setExpanded] = useState<string | null>(null);

  const visible = useMemo(
    () => filterAndSortStories(stories, category, sort),
    [stories, category, sort],
  );

  return (
    <div className="space-y-6">
      <section className="panel space-y-4 p-5 sm:p-6" aria-label="Snapshot disclosure">
        <div className="flex flex-wrap items-center gap-3">
          <span className="status-chip">
            <span className="status-dot" aria-hidden="true" />
            Fixed snapshot
          </span>
          <span className="font-mono text-xs text-muted">
            {snapshotId} · {formatUtcDate(recordedAt)}
          </span>
        </div>
        <p className="max-w-3xl text-sm leading-relaxed text-muted">{disclaimer}</p>
        <p className="text-sm text-muted">
          Model used for these analyses:{" "}
          <span className="font-mono text-paper/90">
            {modelId} · {quantization}
          </span>
          . Interactions below filter and expand this JSON only — no live model
          calls.
        </p>
      </section>

      <section
        className="panel flex flex-col gap-4 p-4 sm:flex-row sm:items-end sm:justify-between sm:p-5"
        aria-label="Demo controls"
      >
        <div className="grid flex-1 gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1.5 block text-muted">Category</span>
            <select
              className="w-full rounded-lg border border-line bg-ink-soft px-3 py-2.5 text-paper"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="all">All categories</option>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="mb-1.5 block text-muted">Sort by</span>
            <select
              className="w-full rounded-lg border border-line bg-ink-soft px-3 py-2.5 text-paper"
              value={sort}
              onChange={(event) => setSort(event.target.value as DemoSort)}
            >
              <option value="significance">Significance</option>
              <option value="relevance">Relevance</option>
              <option value="published">Publication time</option>
            </select>
          </label>
        </div>
        <p className="text-sm text-muted" role="status" aria-live="polite">
          Showing {visible.length} of {stories.length} stories
        </p>
      </section>

      {visible.length === 0 ? (
        <div className="panel p-8 text-center" role="status">
          <p className="font-display text-2xl text-paper">No stories match</p>
          <p className="mt-2 text-sm text-muted">
            Try another category. This snapshot is fixed — new analyses are not
            generated here.
          </p>
          <button
            type="button"
            className="btn-secondary mt-5"
            onClick={() => setCategory("all")}
          >
            Reset category filter
          </button>
        </div>
      ) : (
        <ul className="space-y-4">
          {visible.map((story) => {
            const open = expanded === story.id;
            const href = safeSourceHref(story.source_url);
            const panelId = `${story.id}-details`;
            return (
              <li key={story.id} className="panel overflow-hidden">
                <div className="space-y-4 p-5 sm:p-6">
                  <div className="flex flex-wrap items-center gap-2 text-[0.7rem] uppercase tracking-[0.12em] text-muted">
                    <span className="rounded-full border border-line px-2.5 py-1 text-accent">
                      {story.category}
                    </span>
                    <span>{story.source_name}</span>
                    <span aria-hidden="true">·</span>
                    <span>{formatUtcDate(story.published_at)}</span>
                    <span aria-hidden="true">·</span>
                    <span>evidence {story.evidence_sufficiency}</span>
                  </div>
                  <h2 className="text-2xl leading-snug sm:text-[1.7rem]">
                    {story.headline}
                  </h2>
                  <p className="max-w-3xl text-sm leading-relaxed text-muted sm:text-base">
                    {story.summary}
                  </p>
                  <div className="flex flex-wrap gap-4 text-sm text-muted">
                    <span>
                      Significance{" "}
                      <strong className="font-medium text-paper">
                        {scoreLabel(story.significance_score)}
                      </strong>
                    </span>
                    <span>
                      Relevance{" "}
                      <strong className="font-medium text-paper">
                        {scoreLabel(story.relevance_score)}
                      </strong>
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      className="btn-secondary"
                      aria-expanded={open}
                      aria-controls={panelId}
                      onClick={() =>
                        setExpanded((current) =>
                          current === story.id ? null : story.id,
                        )
                      }
                    >
                      {open ? "Hide details" : "Expand details"}
                    </button>
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn-primary no-underline"
                      >
                        Original source
                      </a>
                    ) : (
                      <span className="text-sm text-warn">
                        Source link unavailable
                      </span>
                    )}
                  </div>
                </div>

                {open ? (
                  <div
                    id={panelId}
                    className="space-y-4 border-t border-line/80 bg-ink-soft/35 px-5 py-5 sm:px-6"
                  >
                    <div>
                      <h3 className="text-sm font-medium text-paper">
                        Why it matters
                      </h3>
                      <p className="mt-2 text-sm leading-relaxed text-muted">
                        {story.why_it_matters}
                      </p>
                    </div>
                    {story.key_claims && story.key_claims.length > 0 ? (
                      <div>
                        <h3 className="text-sm font-medium text-paper">
                          Key claims from source text
                        </h3>
                        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
                          {story.key_claims.map((claim) => (
                            <li key={claim}>{claim}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {story.limitations ? (
                      <div>
                        <h3 className="text-sm font-medium text-paper">
                          Limitations / uncertainty
                        </h3>
                        <p className="mt-2 text-sm leading-relaxed text-muted">
                          {story.limitations}
                        </p>
                      </div>
                    ) : null}
                    <p className="text-xs text-muted">{story.disclaimer}</p>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
