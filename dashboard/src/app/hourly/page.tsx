import { ReportRow } from "@/components/ReportRow";
import { StateBanner } from "@/components/StateBanner";
import { fetchHourly, getApiBase } from "@/lib/api";
import type { ReportSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function HourlyPage() {
  let items: ReportSummary[] = [];
  let error: string | null = null;
  try {
    const data = await fetchHourly(30);
    items = data.items;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load hourly reports";
  }

  const nonempty = items.filter((i) => i.kind !== "empty");
  const empty = items.filter((i) => i.kind === "empty");

  return (
    <>
      <h1 className="page-title">Hourly updates</h1>
      <p className="lede">
        Chronological hourly deltas. Empty cycles are listed separately so quiet hours
        do not drown out real developments.
      </p>
      {error ? (
        <StateBanner kind="error">
          API unavailable at {getApiBase()}: {error}
        </StateBanner>
      ) : null}

      {!error && items.length === 0 ? (
        <p className="empty">No hourly reports stored yet.</p>
      ) : null}

      {nonempty.length > 0 ? (
        <section className="timeline" aria-label="Hourly developments">
          <h2 className="page-title" style={{ fontSize: "1.25rem" }}>
            New & significant
          </h2>
          {nonempty.map((r) => (
            <ReportRow key={r.id} report={r} />
          ))}
        </section>
      ) : null}

      {empty.length > 0 ? (
        <section className="timeline" aria-label="Quiet hourly cycles" style={{ marginTop: "2rem" }}>
          <h2 className="page-title" style={{ fontSize: "1.25rem" }}>
            No-update cycles
          </h2>
          {empty.map((r) => (
            <ReportRow key={r.id} report={r} />
          ))}
        </section>
      ) : null}
    </>
  );
}
