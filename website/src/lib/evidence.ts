/**
 * Verified engineering evidence for the public site.
 * Only include figures that are documented in repository milestone notes
 * or reproducible local measurements.
 */
export const engineeringEvidence = [
  {
    label: "Local model",
    value: "Qwen3 4B · Q4_K_M",
    detail:
      "Exact Ollama model id `qwen3:4b`, quantization Q4_K_M (documented in M1).",
  },
  {
    label: "Generation speed",
    value: "~42–45 tok/s",
    detail:
      "Observed eval tokens/sec across the five-article M1 live benchmark (think=false).",
  },
  {
    label: "M1 five-article run",
    value: "45.8 s sequential",
    detail:
      "Wall time 45.81s for five sequential analyses on the M1 benchmark set.",
  },
  {
    label: "News sources",
    value: "5 configured",
    detail:
      "Hacker News, OpenAI, Google DeepMind, Hugging Face, and TechCrunch AI RSS.",
  },
  {
    label: "Python tests",
    value: "124 collected",
    detail:
      "Historical M4.2-era suite size: `pytest --collect-only` reports 124 tests in this checkout. Not a live counter.",
  },
] as const;

export const evidenceConditions = [
  "M1 live benchmark: five articles, sequential concurrency=1, think=false, local Ollama.",
  "Token/sec figures are per-article eval rates from `data/reports/live_m1_benchmark.json`.",
  "Test count is a collected suite size at verification time, not continuously measured CI output on this static site.",
] as const;
