"use client";

import { useId, useState } from "react";
import {
  BACKLOG_INITIAL_PENDING,
  BACKLOG_MAX_ANALYZE,
  countByStatus,
  createInitialBacklogState,
  runBacklogCycle,
  type BacklogState,
} from "@/lib/backlog";

export function BacklogExplorer() {
  const baseId = useId();
  const [state, setState] = useState<BacklogState>(() =>
    createInitialBacklogState(),
  );
  const [simulateFailure, setSimulateFailure] = useState(false);
  const counts = countByStatus(state);
  const total = Math.max(counts.pending + counts.failed + counts.processed, 1);

  return (
    <section className="space-y-6" aria-labelledby={`${baseId}-heading`}>
      <div className="max-w-3xl">
        <h2 id={`${baseId}-heading`} className="text-3xl sm:text-4xl">
          Interactive backlog explorer
        </h2>
        <p className="mt-3 text-muted">
          Teaching simulation of M3.1 backlog caps and watermark safety. Starts
          with {BACKLOG_INITIAL_PENDING} pending articles and processes at most{" "}
          {BACKLOG_MAX_ANALYZE} per cycle.{" "}
          <strong className="font-medium text-paper">
            Not a live view of your database.
          </strong>
        </p>
      </div>

      <div className="panel space-y-5 p-5 sm:p-7">
        <div className="flex flex-wrap items-center gap-3">
          <span className="status-chip">
            <span className="status-dot" aria-hidden="true" />
            Simulation · M3.1 behavior
          </span>
          <span className="font-mono text-xs text-muted">
            cycle {state.cycle} · watermark {state.watermark}
          </span>
        </div>

        <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Pending" value={String(counts.pending)} />
          <Stat label="Processed" value={String(counts.processed)} />
          <Stat label="Failed / retryable" value={String(counts.failed)} />
          <Stat
            label="Watermark"
            value={state.watermark === "advanced" ? "advanced" : "frozen"}
          />
        </dl>

        <p className="text-sm text-muted" role="status" aria-live="polite">
          {state.lastOutcome
            ? `Last outcome: ${state.lastOutcome}. Work cannot be skipped: remaining pending or failed items keep the watermark frozen until the backlog drains and a report persist is simulated.`
            : "Watermark stays frozen while pending or failed work remains. Each cycle analyzes at most five pending or retryable items."}
        </p>

        <div
          className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center"
          role="group"
          aria-label="Backlog simulation controls"
        >
          <button
            type="button"
            className="btn-primary"
            onClick={() =>
              setState((current) =>
                runBacklogCycle(current, { simulateFailure }),
              )
            }
          >
            Next cycle
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => {
              setSimulateFailure(false);
              setState(createInitialBacklogState());
            }}
          >
            Reset
          </button>
          <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-line bg-ink-soft accent-[rgb(var(--color-accent))]"
              checked={simulateFailure}
              onChange={(event) => setSimulateFailure(event.target.checked)}
            />
            Simulate analysis failure on next cycle
          </label>
        </div>

        <div className="overflow-hidden rounded-2xl border border-line">
          <div
            className="flex h-3 w-full"
            role="img"
            aria-label={`Backlog composition: ${counts.pending} pending, ${counts.failed} failed, ${counts.processed} processed`}
          >
            <div
              className="bg-accent/70 motion-safe:transition-[flex-grow] motion-safe:duration-300"
              style={{ flexGrow: counts.pending / total, flexBasis: 0 }}
            />
            <div
              className="bg-warn/70 motion-safe:transition-[flex-grow] motion-safe:duration-300"
              style={{ flexGrow: counts.failed / total, flexBasis: 0 }}
            />
            <div
              className="bg-ok/70 motion-safe:transition-[flex-grow] motion-safe:duration-300"
              style={{ flexGrow: counts.processed / total, flexBasis: 0 }}
            />
          </div>
          <p className="border-t border-line/70 px-4 py-2 text-xs text-muted">
            Bar proportions: pending (accent) · failed (warn) · processed (ok)
          </p>
        </div>

        <div>
          <h3 className="text-sm font-medium text-paper">Cycle log</h3>
          <ol className="mt-2 max-h-48 list-decimal space-y-1 overflow-y-auto pl-5 text-sm text-muted">
            {state.log.map((entry, index) => (
              <li key={`${index}-${entry}`}>{entry}</li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line/80 bg-ink-soft/40 p-4">
      <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-muted">
        {label}
      </dt>
      <dd className="mt-1 font-display text-2xl text-paper">{value}</dd>
    </div>
  );
}
