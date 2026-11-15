import Link from "next/link";
import { MarkdownReport } from "@/components/MarkdownReport";
import { ReportMeta } from "@/components/ReportMeta";
import { StateBanner } from "@/components/StateBanner";
import { fetchReport, getApiBase } from "@/lib/api";
import { formatWhen } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const reportId = Number(id);
  if (!Number.isFinite(reportId)) {
    return <StateBanner kind="error">Invalid report id.</StateBanner>;
  }

  try {
    const report = await fetchReport(reportId);
    const generated = report.as_of || report.created_at;
    return (
      <>
        <p>
          <Link href="/history">← History</Link>
        </p>
        <h1 className="page-title">
          {(report.mode || "report").toUpperCase()} · #{report.id}
        </h1>
        <p className="lede">
          Saved Markdown briefing. Times below are <em>report generation</em> times from the
          local store — not article publication dates. Source links open only when the URL is
          http(s).
        </p>
        <ReportMeta
          mode={report.mode}
          generatedAt={generated}
          windowStart={report.window_start}
          storyCount={report.story_count}
          kind={report.kind}
        />
        {!report.markdown?.trim() ? (
          <StateBanner kind="warn">
            Report #{report.id} has an empty Markdown body (generated{" "}
            {formatWhen(generated)}).
          </StateBanner>
        ) : null}
        <MarkdownReport markdown={report.markdown || ""} />
      </>
    );
  } catch (err) {
    return (
      <StateBanner kind="error">
        Could not load report from {getApiBase()}:{" "}
        {err instanceof Error ? err.message : "unknown error"}. Start the stack with{" "}
        <code>python -m qwennews dashboard</code>.
      </StateBanner>
    );
  }
}
