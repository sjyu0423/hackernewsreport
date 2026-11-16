import { describe, expect, it } from "vitest";
import {
  m1ArticleBenchmarks,
  m1BenchmarkMeta,
  m3ObservedCycles,
  testSuiteSnapshots,
} from "./benchmarks";

describe("m1ArticleBenchmarks", () => {
  it("publishes the five verified sequential articles", () => {
    expect(m1ArticleBenchmarks.map((row) => row.source)).toEqual([
      "hackernews",
      "techcrunch",
      "huggingface",
      "openai",
      "deepmind",
    ]);
    expect(m1ArticleBenchmarks[0]?.latencySeconds).toBe(6.4);
    expect(m1ArticleBenchmarks[0]?.tokensPerSecond).toBe(45.0);
    expect(m1BenchmarkMeta.totalSeconds).toBe(45.8);
    expect(m1BenchmarkMeta.modelId).toBe("qwen3:4b");
    expect(m1BenchmarkMeta.think).toBe(false);
    expect(m1BenchmarkMeta.concurrency).toBe(1);
  });

  it("does not invent hardware details", () => {
    const blob = JSON.stringify({ m1ArticleBenchmarks, m1BenchmarkMeta });
    expect(blob.toLowerCase()).not.toMatch(/rtx|m[123]\s*(pro|max|ultra)|nvidia|apple silicon/);
  });
});

describe("m3ObservedCycles", () => {
  it("documents active and quiet cycles as different workloads", () => {
    expect(m3ObservedCycles).toHaveLength(2);
    expect(m3ObservedCycles[0]?.durationSeconds).toBe(35.4);
    expect(m3ObservedCycles[0]?.analyses).toBe(5);
    expect(m3ObservedCycles[1]?.durationSeconds).toBe(0.12);
    expect(m3ObservedCycles[1]?.analyses).toBe(0);
  });
});

describe("testSuiteSnapshots", () => {
  it("uses dated snapshots rather than implying live counters", () => {
    for (const row of testSuiteSnapshots) {
      expect(row.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(row.count).toBeGreaterThan(0);
      expect(row.source.length).toBeGreaterThan(0);
    }
  });
});
