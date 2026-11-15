import Link from "next/link";
import type { ReportSummary } from "@/lib/types";
import { formatWhen } from "@/lib/format";

function kindLabel(kind: string | null): string {
  if (kind === "empty") return "No updates";
  if (kind === "new") return "New developments";
  if (kind === "update") return "Significant updates";
  return kind || "Report";
}

export function ReportRow({ report }: { report: ReportSummary }) {
  const kind = report.kind || "unknown";
  return (
    <div className="report-row">
      <div className="when">{formatWhen(report.as_of || report.created_at)}</div>
      <div>
        <h3>
          <Link href={`/history/${report.id}`}>
            {(report.mode || "report").toUpperCase()} · {kindLabel(kind)}
          </Link>
        </h3>
        <p className={`kind-${kind}`}>
          {report.story_count === 1 ? "1 story" : `${report.story_count} stories`}
          {report.window_start ? ` · from ${formatWhen(report.window_start)}` : ""}
        </p>
      </div>
      <div>
        <Link href={`/history/${report.id}`}>Open</Link>
      </div>
    </div>
  );
}
