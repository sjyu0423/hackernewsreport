import { ReportRow } from "@/components/ReportRow";
import { StateBanner } from "@/components/StateBanner";
import { fetchHistory, getApiBase } from "@/lib/api";
import type { ReportSummary } from "@/lib/types";
import { HistoryFilters } from "./HistoryFilters";

export const dynamic = "force-dynamic";

export default async function HistoryPage({
  searchParams,
}: {
  searchParams: Promise<{ mode?: string; category?: string }>;
}) {
  const params = await searchParams;
  let items: ReportSummary[] = [];
  let categories: string[] = [];
  let error: string | null = null;
  try {
    const data = await fetchHistory({
      mode: params.mode || undefined,
      category: params.category || undefined,
      limit: 50,
    });
    items = data.items;
    categories = data.categories;
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load history";
  }

  return (
    <>
      <h1 className="page-title">History</h1>
      <p className="lede">
        Browse prior daily and hourly briefings. Open any report for the full stored
        Markdown and source links embedded in it.
      </p>
      <HistoryFilters categories={categories} mode={params.mode} category={params.category} />
      {error ? (
        <StateBanner kind="error">
          API unavailable at {getApiBase()}: {error}
        </StateBanner>
      ) : null}
      {!error && items.length === 0 ? (
        <p className="empty">No matching reports.</p>
      ) : (
        <section className="timeline" aria-label="Report history">
          {items.map((r) => (
            <ReportRow key={r.id} report={r} />
          ))}
        </section>
      )}
    </>
  );
}
