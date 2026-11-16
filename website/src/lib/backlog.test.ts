import { describe, expect, it } from "vitest";
import {
  BACKLOG_INITIAL_PENDING,
  BACKLOG_MAX_ANALYZE,
  countByStatus,
  createInitialBacklogState,
  cyclesToDrain,
  runBacklogCycle,
} from "./backlog";

describe("createInitialBacklogState", () => {
  it("starts with 25 pending items and a frozen watermark", () => {
    const state = createInitialBacklogState();
    const counts = countByStatus(state);
    expect(counts).toEqual({
      pending: BACKLOG_INITIAL_PENDING,
      processed: 0,
      failed: 0,
    });
    expect(state.watermark).toBe("frozen");
    expect(state.maxAnalyze).toBe(BACKLOG_MAX_ANALYZE);
    expect(state.cycle).toBe(0);
    expect(state.reportPersisted).toBe(false);
  });
});

describe("runBacklogCycle", () => {
  it("processes at most five items per cycle and keeps watermark frozen", () => {
    let state = createInitialBacklogState();
    state = runBacklogCycle(state);
    const counts = countByStatus(state);
    expect(counts.processed).toBe(5);
    expect(counts.pending).toBe(20);
    expect(state.lastOutcome).toBe("backlog_remaining");
    expect(state.watermark).toBe("frozen");
    expect(state.lastProcessed).toBe(5);
    expect(state.cycle).toBe(1);
  });

  it("does not skip work — five successful cycles drain 25 pending", () => {
    let state = createInitialBacklogState();
    expect(cyclesToDrain()).toBe(5);

    for (let i = 0; i < 4; i += 1) {
      state = runBacklogCycle(state);
      expect(state.watermark).toBe("frozen");
      expect(state.lastOutcome).toBe("backlog_remaining");
    }

    state = runBacklogCycle(state);
    const counts = countByStatus(state);
    expect(counts).toEqual({ pending: 0, processed: 25, failed: 0 });
    expect(state.lastOutcome).toBe("success");
    expect(state.watermark).toBe("advanced");
    expect(state.reportPersisted).toBe(true);
    expect(state.cycle).toBe(5);
  });

  it("marks selected items failed and retryable when simulateFailure is set", () => {
    let state = createInitialBacklogState();
    state = runBacklogCycle(state, { simulateFailure: true });
    const counts = countByStatus(state);
    expect(counts.failed).toBe(5);
    expect(counts.pending).toBe(20);
    expect(counts.processed).toBe(0);
    expect(state.lastOutcome).toBe("analyze_failed");
    expect(state.watermark).toBe("frozen");
    expect(state.reportPersisted).toBe(false);
  });

  it("retries failed items before remaining pending on the next cycle", () => {
    let state = createInitialBacklogState();
    state = runBacklogCycle(state, { simulateFailure: true });
    state = runBacklogCycle(state);
    const counts = countByStatus(state);
    expect(counts.failed).toBe(0);
    expect(counts.processed).toBe(5);
    expect(counts.pending).toBe(20);
    expect(state.watermark).toBe("frozen");
  });

  it("keeps watermark frozen while failed retryables remain", () => {
    let state = createInitialBacklogState(5);
    state = runBacklogCycle(state, { simulateFailure: true });
    expect(countByStatus(state).failed).toBe(5);
    expect(state.watermark).toBe("frozen");

    state = runBacklogCycle(state);
    expect(countByStatus(state)).toEqual({
      pending: 0,
      processed: 5,
      failed: 0,
    });
    expect(state.lastOutcome).toBe("success");
    expect(state.watermark).toBe("advanced");
  });

  it("returns empty_success after drain without republishing", () => {
    let state = createInitialBacklogState(3, 5);
    state = runBacklogCycle(state);
    expect(state.watermark).toBe("advanced");
    expect(state.lastOutcome).toBe("success");

    state = runBacklogCycle(state);
    expect(state.lastOutcome).toBe("empty_success");
    expect(state.watermark).toBe("advanced");
    expect(state.lastProcessed).toBe(0);
  });
});
