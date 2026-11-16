/**
 * Deterministic teaching simulation of M3.1 backlog + watermark behavior.
 * Not connected to any live SQLite database.
 */

export const BACKLOG_INITIAL_PENDING = 25;
export const BACKLOG_MAX_ANALYZE = 5;

export type BacklogItemStatus = "pending" | "processed" | "failed";

export type BacklogItem = {
  id: number;
  status: BacklogItemStatus;
};

export type WatermarkState = "frozen" | "advanced";

export type CycleOutcome =
  | "backlog_remaining"
  | "success"
  | "empty_success"
  | "analyze_failed";

export type BacklogState = {
  items: BacklogItem[];
  cycle: number;
  maxAnalyze: number;
  watermark: WatermarkState;
  lastOutcome: CycleOutcome | null;
  lastProcessed: number;
  lastFailed: number;
  reportPersisted: boolean;
  log: string[];
};

export function createInitialBacklogState(
  pendingCount = BACKLOG_INITIAL_PENDING,
  maxAnalyze = BACKLOG_MAX_ANALYZE,
): BacklogState {
  return {
    items: Array.from({ length: pendingCount }, (_, index) => ({
      id: index + 1,
      status: "pending",
    })),
    cycle: 0,
    maxAnalyze,
    watermark: "frozen",
    lastOutcome: null,
    lastProcessed: 0,
    lastFailed: 0,
    reportPersisted: false,
    log: [
      `Simulation ready: ${pendingCount} pending articles, max ${maxAnalyze} analyses/cycle, watermark frozen.`,
    ],
  };
}

export function countByStatus(state: BacklogState): {
  pending: number;
  processed: number;
  failed: number;
} {
  let pending = 0;
  let processed = 0;
  let failed = 0;
  for (const item of state.items) {
    if (item.status === "pending") pending += 1;
    else if (item.status === "processed") processed += 1;
    else failed += 1;
  }
  return { pending, processed, failed };
}

function selectableIds(state: BacklogState): number[] {
  const failed = state.items
    .filter((item) => item.status === "failed")
    .map((item) => item.id);
  const pending = state.items
    .filter((item) => item.status === "pending")
    .map((item) => item.id);
  return [...failed, ...pending];
}

export function runBacklogCycle(
  state: BacklogState,
  options: { simulateFailure?: boolean } = {},
): BacklogState {
  const simulateFailure = Boolean(options.simulateFailure);
  const counts = countByStatus(state);

  if (counts.pending === 0 && counts.failed === 0) {
    if (state.watermark === "advanced") {
      return {
        ...state,
        lastOutcome: "empty_success",
        lastProcessed: 0,
        lastFailed: 0,
        log: [
          ...state.log,
          `Cycle ${state.cycle + 1}: backlog already drained; empty_success (no republish).`,
        ],
        cycle: state.cycle + 1,
      };
    }

    return {
      ...state,
      cycle: state.cycle + 1,
      watermark: "advanced",
      reportPersisted: true,
      lastOutcome: "success",
      lastProcessed: 0,
      lastFailed: 0,
      log: [
        ...state.log,
        `Cycle ${state.cycle + 1}: backlog drained; report persisted; watermark advanced.`,
      ],
    };
  }

  const selected = selectableIds(state).slice(0, state.maxAnalyze);
  const selectedSet = new Set(selected);
  const nextStatus: BacklogItemStatus = simulateFailure ? "failed" : "processed";

  const items = state.items.map((item) =>
    selectedSet.has(item.id) ? { ...item, status: nextStatus } : item,
  );

  const nextCounts = {
    pending: items.filter((item) => item.status === "pending").length,
    failed: items.filter((item) => item.status === "failed").length,
    processed: items.filter((item) => item.status === "processed").length,
  };

  const drained = nextCounts.pending === 0 && nextCounts.failed === 0;

  if (simulateFailure) {
    return {
      ...state,
      items,
      cycle: state.cycle + 1,
      watermark: "frozen",
      reportPersisted: false,
      lastOutcome: "analyze_failed",
      lastProcessed: 0,
      lastFailed: selected.length,
      log: [
        ...state.log,
        `Cycle ${state.cycle + 1}: simulated analysis failure on ${selected.length} item(s); watermark frozen; work stays retryable.`,
      ],
    };
  }

  if (!drained) {
    return {
      ...state,
      items,
      cycle: state.cycle + 1,
      watermark: "frozen",
      reportPersisted: false,
      lastOutcome: "backlog_remaining",
      lastProcessed: selected.length,
      lastFailed: 0,
      log: [
        ...state.log,
        `Cycle ${state.cycle + 1}: processed ${selected.length}; pending ${nextCounts.pending}; failed ${nextCounts.failed}; watermark frozen (backlog_remaining).`,
      ],
    };
  }

  return {
    ...state,
    items,
    cycle: state.cycle + 1,
    watermark: "advanced",
    reportPersisted: true,
    lastOutcome: "success",
    lastProcessed: selected.length,
    lastFailed: 0,
    log: [
      ...state.log,
      `Cycle ${state.cycle + 1}: processed final ${selected.length}; backlog drained; report persisted; watermark advanced.`,
    ],
  };
}

export function cyclesToDrain(
  pendingCount = BACKLOG_INITIAL_PENDING,
  maxAnalyze = BACKLOG_MAX_ANALYZE,
): number {
  return Math.ceil(pendingCount / maxAnalyze);
}
