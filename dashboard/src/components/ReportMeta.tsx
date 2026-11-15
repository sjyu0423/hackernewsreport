import { formatWhen } from "@/lib/format";

/** Distinguish report generation time from article publication time. */
export function ReportMeta({
  generatedAt,
  windowStart,
  storyCount,
  kind,
  mode,
}: {
  generatedAt: string | null | undefined;
  windowStart?: string | null;
  storyCount?: number;
  kind?: string | null;
  mode?: string | null;
}) {
  return (
    <dl className="report-meta">
      {mode ? (
        <>
          <dt>Report type</dt>
          <dd>{mode.toUpperCase()}</dd>
        </>
      ) : null}
      <dt>Generated</dt>
      <dd>
        <time dateTime={generatedAt || undefined}>{formatWhen(generatedAt)}</time>
        <span className="meta-hint"> report generation time</span>
      </dd>
      {windowStart ? (
        <>
          <dt>Window start</dt>
          <dd>
            <time dateTime={windowStart}>{formatWhen(windowStart)}</time>
          </dd>
        </>
      ) : null}
      {typeof storyCount === "number" ? (
        <>
          <dt>Stories listed</dt>
          <dd>{storyCount}</dd>
        </>
      ) : null}
      {kind ? (
        <>
          <dt>Kind</dt>
          <dd>{kind}</dd>
        </>
      ) : null}
    </dl>
  );
}
