export type Tradeoff = {
  id: string;
  title: string;
  gain: string;
  cost: string;
};

export const engineeringTradeoffs: Tradeoff[] = [
  {
    id: "local-inference",
    title: "Local inference",
    gain: "Privacy and control: article text stays on the machine; no cloud inference dependency.",
    cost: "Requires a healthy local Ollama process and accepts device-bound latency.",
  },
  {
    id: "sqlite",
    title: "SQLite persistence",
    gain: "Simple durable state for a single-operator Mac deployment without a separate DB service.",
    cost: "Not aimed at multi-writer horizontal scale; operators must back up the DB intentionally.",
  },
  {
    id: "near-dupes",
    title: "Conservative lexical near-duplicates",
    gain: "Fewer false merges across unrelated stories; HN score churn stays UNCHANGED.",
    cost: "Some true duplicates may remain separate until stronger semantic linking exists.",
  },
  {
    id: "deterministic-ranking",
    title: "Deterministic ranking & report formatting",
    gain: "Reproducible briefings and auditable selection rules outside the model.",
    cost: "Limited semantic nuance versus a model-chosen layout or embedding reranker.",
  },
  {
    id: "small-model",
    title: "Small local language model (Qwen3 4B)",
    gain: "Affordable local inference with structured JSON validation and caching.",
    cost: "Weaker reasoning/grounding than larger models; thin pages are labeled insufficient rather than invented.",
  },
];

export const evaluationCaveat =
  "Comprehensive factual-accuracy and news-relevance evaluation remain future research. Public metrics here are runtime/orchestration measurements, not claim-level truth scores.";
