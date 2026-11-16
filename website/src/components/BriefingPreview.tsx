import Link from "next/link";
import type { DemoStory } from "@/lib/demo";
import { safeSourceHref } from "@/lib/demo";
import { formatUtcDate, scoreLabel } from "@/lib/format";

type BriefingPreviewProps = {
  stories: DemoStory[];
  snapshotId: string;
  recordedAt: string;
};

export function BriefingPreview({
  stories,
  snapshotId,
  recordedAt,
}: BriefingPreviewProps) {
  return (
    <aside
      className="panel overflow-hidden"
      aria-label="Sample briefing preview"
    >
      <div className="border-b border-line/80 px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow">Sample briefing</p>
            <p className="mt-1 font-display text-xl text-paper">
              Fixed snapshot preview
            </p>
          </div>
          <span className="status-chip">
            <span className="status-dot" aria-hidden="true" />
            Not live
          </span>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-muted">
          Snapshot <span className="font-mono text-paper/80">{snapshotId}</span>
          {" · "}
          recorded {formatUtcDate(recordedAt)}. Analyses were produced locally
          by Qwen3 4B; this page only renders the saved JSON.
        </p>
      </div>

      <ol className="divide-y divide-line/70">
        {stories.map((story, index) => {
          const href = safeSourceHref(story.source_url);
          return (
            <li key={story.id} className="px-5 py-4 sm:px-6">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 font-mono text-xs text-accent">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="flex flex-wrap gap-2 text-[0.7rem] uppercase tracking-[0.12em] text-muted">
                    <span>{story.category}</span>
                    <span aria-hidden="true">·</span>
                    <span>{story.source_name}</span>
                    <span aria-hidden="true">·</span>
                    <span>sig {scoreLabel(story.significance_score)}</span>
                  </div>
                  <h3 className="text-base leading-snug text-paper sm:text-lg">
                    {story.headline}
                  </h3>
                  <p className="line-clamp-3 text-sm leading-relaxed text-muted">
                    {story.summary}
                  </p>
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex text-sm no-underline"
                    >
                      Original source
                      <span className="sr-only"> for {story.headline}</span>
                    </a>
                  ) : null}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="border-t border-line/80 bg-ink-soft/40 px-5 py-4 sm:px-6">
        <Link href="/demo/" className="btn-primary no-underline">
          Open interactive demo
        </Link>
      </div>
    </aside>
  );
}
