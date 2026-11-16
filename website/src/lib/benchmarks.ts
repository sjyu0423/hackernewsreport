/**
 * Verified public-site benchmarks only.
 * Prefer milestone docs + committed JSON; qualify session observations.
 */

export type M1ArticleBenchmark = {
  source: string;
  label: string;
  latencySeconds: number;
  tokensPerSecond: number;
  evidence: string;
};

/** Rounded display values from M1 table / live_m1_benchmark.json (2026-11-15). */
export const m1ArticleBenchmarks: M1ArticleBenchmark[] = [
  {
    source: "hackernews",
    label: "Hacker News",
    latencySeconds: 6.4,
    tokensPerSecond: 45.0,
    evidence: "insufficient",
  },
  {
    source: "techcrunch",
    label: "TechCrunch",
    latencySeconds: 11.7,
    tokensPerSecond: 43.7,
    evidence: "partial",
  },
  {
    source: "huggingface",
    label: "Hugging Face",
    latencySeconds: 8.2,
    tokensPerSecond: 41.8,
    evidence: "partial",
  },
  {
    source: "openai",
    label: "OpenAI",
    latencySeconds: 8.6,
    tokensPerSecond: 42.5,
    evidence: "sufficient",
  },
  {
    source: "deepmind",
    label: "DeepMind",
    latencySeconds: 10.9,
    tokensPerSecond: 42.6,
    evidence: "sufficient",
  },
];

export const m1BenchmarkMeta = {
  totalSeconds: 45.8,
  totalSecondsExact: 45.81,
  modelId: "qwen3:4b",
  quantization: "Q4_K_M",
  think: false,
  concurrency: 1,
  date: "2026-11-15",
  sources: [
    "docs/milestones/m1.md",
    "Committed M1 benchmark JSON under data/reports/ (local checkout; not bundled in this static site)",
  ],
  conditions: [
    "Five articles analyzed sequentially on local Ollama",
    "Thinking mode disabled (think=false)",
    "Latency is per-article wall/latency seconds from the M1 live benchmark",
    "tok/s is Ollama eval tokens/sec for that article",
    "No hardware SKU / GPU model claims are published — those were not recorded in milestone docs",
  ],
} as const;

export const m3ObservedCycles = [
  {
    id: "active",
    title: "Active M3 cycle",
    durationSeconds: 35.4,
    analyses: 5,
    note: "Manual `run-hourly --max-analyze 5` during M3 verification inferred five articles.",
  },
  {
    id: "quiet",
    title: "Quiet M3 cycle",
    durationSeconds: 0.12,
    analyses: 0,
    note: "Later unchanged hourly cycle inferred zero articles (~120ms).",
  },
] as const;

export const m3CycleCaveat =
  "These are different workloads (work to do vs nothing eligible), not a controlled A/B speedup comparison. Behavior is documented in docs/milestones/m3.md; wall times were recorded in the 2026-11-15 M3 verification session.";

export const testSuiteSnapshots = [
  {
    milestone: "M1",
    date: "2026-11-15",
    count: 59,
    kind: "pytest passed",
    source: "docs/milestones/m1.md",
  },
  {
    milestone: "M3",
    date: "2026-11-15",
    count: 86,
    kind: "pytest passed",
    source: "M3 verification report",
  },
  {
    milestone: "M3.1",
    date: "2026-11-15",
    count: 92,
    kind: "pytest passed",
    source: "M3.1 verification report",
  },
  {
    milestone: "M4.2-era checkout",
    date: "2026-11-16",
    count: 124,
    kind: "pytest collected",
    source: "pytest --collect-only during W1 website verification",
  },
] as const;

export const githubDocLinks = {
  architecture: "https://github.com/sjyu0423/hackernewsreport/blob/milestone-4-2-production-reliability/docs/architecture.md",
  m1: "https://github.com/sjyu0423/hackernewsreport/blob/milestone-4-2-production-reliability/docs/milestones/m1.md",
  m3: "https://github.com/sjyu0423/hackernewsreport/blob/milestone-4-2-production-reliability/docs/milestones/m3.md",
  m4_2: "https://github.com/sjyu0423/hackernewsreport/blob/milestone-4-2-production-reliability/docs/milestones/m4_2.md",
} as const;
