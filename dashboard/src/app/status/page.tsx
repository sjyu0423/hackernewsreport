import { StateBanner } from "@/components/StateBanner";
import { fetchStatus, getApiBase } from "@/lib/api";
import { formatWhen } from "@/lib/format";

export const dynamic = "force-dynamic";

function triggerLabel(raw: unknown): string {
  const v = String(raw || "unrecorded");
  if (v === "launchd") return "timer/LaunchAgent";
  if (v === "cli" || v === "manual") return "manual CLI";
  if (v === "kickstart") return "kickstart (not a timer proof)";
  if (v === "unrecorded") return "unrecorded (pre-M4.2 or unknown)";
  return v;
}

function verificationBannerKind(
  code: string | undefined,
): "info" | "warn" | "error" {
  if (code === "timer_evidence") return "info";
  if (code === "due_but_no_fire" || code === "missing_plist") return "error";
  return "warn";
}

export default async function StatusPage() {
  try {
    const status = await fetchStatus();
    const backlog = status.backlog || {};
    const ollama = status.ollama || {};
    const runs = status.recent_runs || [];
    const scheduler = status.scheduler || {};
    const hourlySched = (scheduler.hourly || {}) as Record<string, unknown>;
    const dailySched = (scheduler.daily || {}) as Record<string, unknown>;
    const volume = status.volume || {};

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
            <div className="label">Database</div>
            <div className="value" style={{ fontSize: "1rem" }}>
              {String(status.db.db_path_name ?? "—")}
            </div>
            <div className="meta-hint" style={{ marginTop: "0.35rem" }}>
              {String(status.db.db_path ?? "")}
              {status.db.is_canonical_production_name
                ? " · canonical production file"
                : " · not the canonical live_m0.db name"}
            </div>
          </div>
        </div>

        <StateBanner kind={volume.ok ? "info" : "error"}>
          Project volume: {volume.ok ? "available" : "MISSING"} · {String(volume.path || "—")}
        </StateBanner>

        <StateBanner>
          Last hourly report:{" "}
          {status.last_hourly_report
            ? `#${status.last_hourly_report.id} · generated ${formatWhen(status.last_hourly_report.as_of)} · ${status.last_hourly_report.kind}`
            : "none"}
          <br />
          Last daily report:{" "}
          {status.last_daily_report
            ? `#${status.last_daily_report.id} · generated ${formatWhen(status.last_daily_report.as_of)}`
            : "none"}
          <br />
          Last successful hourly run:{" "}
          {status.last_successful_hourly_run
            ? `#${status.last_successful_hourly_run.id} · ${formatWhen(String(status.last_successful_hourly_run.finished_at || status.last_successful_hourly_run.started_at || ""))} · ${triggerLabel(status.last_successful_hourly_run.trigger_source)} · ${String(status.last_successful_hourly_run.outcome)}`
            : "none"}
          <br />
          Last successful daily run:{" "}
          {status.last_successful_daily_run
            ? `#${status.last_successful_daily_run.id} · ${formatWhen(String(status.last_successful_daily_run.finished_at || status.last_successful_daily_run.started_at || ""))} · ${triggerLabel(status.last_successful_daily_run.trigger_source)} · ${String(status.last_successful_daily_run.outcome)}`
            : "none"}
        </StateBanner>

        <h2 className="page-title" style={{ fontSize: "1.25rem" }}>
          Scheduler verification
        </h2>
        <p className="lede">
          Loaded LaunchAgents are not proof of unattended execution. Status below comes from
          launchctl runs, agent logs, and due-window estimates — never from a manual kickstart
          alone.
        </p>
        <StateBanner kind={verificationBannerKind(String(hourlySched.verification || ""))}>
          <strong>Hourly</strong> · {String(hourlySched.verification || "unknown")}
          <br />
          {String(hourlySched.verification_reason || "")}
          <br />
          launchctl runs={String((hourlySched.launchctl as Record<string, unknown> | undefined)?.runs ?? "—")}
          · logs stdout/stderr bytes=
          {String((hourlySched.logs as Record<string, unknown> | undefined)?.stdout_bytes ?? 0)}/
          {String((hourlySched.logs as Record<string, unknown> | undefined)?.stderr_bytes ?? 0)}
          · due={String(hourlySched.due)}
        </StateBanner>
        <StateBanner kind={verificationBannerKind(String(dailySched.verification || ""))}>
          <strong>Daily</strong> · {String(dailySched.verification || "unknown")}
          <br />
          {String(dailySched.verification_reason || "")}
          <br />
          launchctl runs={String((dailySched.launchctl as Record<string, unknown> | undefined)?.runs ?? "—")}
          · logs stdout/stderr bytes=
          {String((dailySched.logs as Record<string, unknown> | undefined)?.stdout_bytes ?? 0)}/
          {String((dailySched.logs as Record<string, unknown> | undefined)?.stderr_bytes ?? 0)}
          · due={String(dailySched.due)}
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
                    trigger={triggerLabel(run.trigger_source)} · status={String(run.status)} ·
                    empty={String(run.empty_cycle)} · wm_adv={String(run.watermark_advanced)}
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
