import { StateBanner } from "@/components/StateBanner";
import { fetchStatus, getApiBase } from "@/lib/api";
import { formatWhen } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function StatusPage() {
  try {
    const status = await fetchStatus();
    const backlog = status.backlog || {};
    const ollama = status.ollama || {};
    const runs = status.recent_runs || [];

    return (
      <>
        <h1 className="page-title">System status</h1>
        <p className="lede">{status.note}</p>

        <div className="status-grid">
          <div className="stat">
            <div className="label">Articles / analyses</div>
            <div className="value">
              {String(status.db.article_count ?? "—")} / {String(status.db.analysis_count ?? "—")}
            </div>
          </div>
          <div className="stat">
            <div className="label">Active backlog</div>
            <div className="value">{backlog.active ?? 0}</div>
          </div>
          <div className="stat">
            <div className="label">Ollama (live probe)</div>
            <div className="value" style={{ color: ollama.ok ? "var(--ok)" : "var(--danger)" }}>
              {status.ollama_live ? (ollama.ok ? "OK" : "Down") : "Skipped"}
            </div>
          </div>
          <div className="stat">
            <div className="label">Database file</div>
            <div className="value" style={{ fontSize: "1rem" }}>
              {String(status.db.db_path_name ?? "—")}
            </div>
          </div>
        </div>

        <StateBanner>
          Last hourly:{" "}
          {status.last_hourly_report
            ? `#${status.last_hourly_report.id} · ${formatWhen(status.last_hourly_report.as_of)} · ${status.last_hourly_report.kind}`
            : "none"}
          <br />
          Last daily:{" "}
          {status.last_daily_report
            ? `#${status.last_daily_report.id} · ${formatWhen(status.last_daily_report.as_of)}`
            : "none"}
        </StateBanner>

        <h2 className="page-title" style={{ fontSize: "1.25rem" }}>
          Recent orchestration runs
        </h2>
        {runs.length === 0 ? (
          <p className="empty">No orchestration_runs rows yet.</p>
        ) : (
          <div className="timeline">
            {runs.map((run) => (
              <div className="report-row" key={String(run.id)}>
                <div className="when">{formatWhen(String(run.started_at || ""))}</div>
                <div>
                  <h3>
                    {String(run.mode)} · {String(run.outcome)}
                  </h3>
                  <p className="kind-empty">
                    status={String(run.status)} · empty={String(run.empty_cycle)} ·
                    wm_adv={String(run.watermark_advanced)}
                    {run.error ? ` · error=${String(run.error)}` : ""}
                  </p>
                </div>
                <div />
              </div>
            ))}
          </div>
        )}
      </>
    );
  } catch (err) {
    return (
      <>
        <h1 className="page-title">System status</h1>
        <StateBanner kind="error">
          Cannot reach API at {getApiBase()}:{" "}
          {err instanceof Error ? err.message : "unknown error"}. Start with{" "}
          <code>python -m qwennews dashboard</code>.
        </StateBanner>
      </>
    );
  }
}
