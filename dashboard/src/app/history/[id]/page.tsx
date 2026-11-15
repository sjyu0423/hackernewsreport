import Link from "next/link";
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
    return (
      <>
        <p>
          <Link href="/history">← History</Link>
        </p>
        <h1 className="page-title">
          {(report.mode || "report").toUpperCase()} · #{report.id}
        </h1>
        <p className="lede">
          As of {formatWhen(report.as_of || report.created_at)} · {report.story_count}{" "}
          stories · kind {report.kind}
        </p>
        <pre className="markdown" tabIndex={0}>
          {report.markdown}
        </pre>
      </>
    );
  } catch (err) {
    return (
      <StateBanner kind="error">
        Could not load report from {getApiBase()}:{" "}
        {err instanceof Error ? err.message : "unknown error"}
      </StateBanner>
    );
  }
}
