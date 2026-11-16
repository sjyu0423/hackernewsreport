/**
 * Under-the-hood technical content derived from application source.
 * Prefer code + milestone docs over marketing copy when they diverge.
 */

import { githubDocLinks } from "@/lib/benchmarks";

export const underHoodLinks = {
  ...githubDocLinks,
  m2: "https://github.com/sjyu0423/hackernewsreport/blob/milestone-4-2-production-reliability/docs/milestones/m2.md",
} as const;

export const correctedClaims = [
  {
    claim: "SQLite schema is “v5” (backlog era wording in some docs)",
    actual:
      "Current code stamps schema_meta.schema_version = \"6\" (adds orchestration_runs.trigger_source).",
    source: "qwennews/storage.py",
  },
  {
    claim: "Shared story last_reported_at alone separates hourly vs daily",
    actual:
      "M3 introduced story_report_state keyed by (story_id, mode). Legacy last_reported_at may still exist but mode independence is via per-mode rows.",
    source: "qwennews/storage.py, qwennews/report.py",
  },
  {
    claim: "Uncertainty is a rich multi-label taxonomy",
    actual:
      "Uncertainty is evidence_sufficiency (sufficient|partial|insufficient) plus free-text limitations — no separate uncertainty enum.",
    source: "qwennews/analysis_schema.py",
  },
] as const;

export const localInferenceNotes = [
  {
    title: "Pretrained local model",
    body: "Inference uses pretrained qwen3:4b served by Ollama on the machine. This project does not train or fine-tune the model.",
  },
  {
    title: "Structured validation",
    body: "Ollama is asked for JSON matching ANALYSIS_JSON_SCHEMA; responses are validated with Pydantic ArticleAnalysis before persistence.",
  },
  {
    title: "Evidence & uncertainty",
    body: "evidence_sufficiency is sufficient, partial, or insufficient. Thin article bodies (<280 characters) get stronger prompt guidance to prefer uncertainty; limitations is required text.",
  },
  {
    title: "Ownership split",
    body: "Model may emit category, summary, why_it_matters, scores, claims, limitations, and an article_id attempt. The app rebinds article_id to the expected DB id, owns URLs/IDs/timestamps, and assembles report Markdown.",
  },
  {
    title: "Untrusted article text",
    body: "Article bodies are wrapped as UNTRUSTED DATA. System rules tell the model to ignore embedded instructions (prompt-injection limitation: defense-in-depth, not a formal guarantee against all jailbreaks).",
  },
  {
    title: "Cache identity",
    body: "Analyses cache on (article_id, content_hash, model_id, config_version). content_hash covers title, URL, body, publish time, HN fields, and sources. config_version is currently m1.v1.",
  },
] as const;

/** Sanitized schematic — public demo field shapes only; not a live DB dump. */
export const schematicIoExample = {
  label: "Sanitized schematic (public-safe shapes)",
  input: `{
  "title": "Example model announcement",
  "canonical_url": "https://example.com/posts/model-launch",
  "source": "example_rss",
  "published_at": "2026-11-12T12:00:00Z",
  "article_text": "<<truncated untrusted body ≤6000 chars>>"
}`,
  output: `{
  "article_id": "<<app-owned id rebound after validation>>",
  "category": "models",
  "summary": "…",
  "why_it_matters": "…",
  "relevance_score": 4,
  "significance_score": 3,
  "evidence_sufficiency": "sufficient",
  "key_claims": ["…"],
  "limitations": "…"
}`,
  notes: [
    "Schema has no URL fields — links stay application-owned.",
    "Based on ArticleAnalysis / ANALYSIS_JSON_SCHEMA in analysis_schema.py.",
    "Not copied from private logs or production prompts.",
  ],
} as const;

export const analysisFieldOwnership = [
  {
    field: "article_id",
    owner: "Application",
    detail: "SHA-256(canonical_url)[:32]; model attempt is overwritten on validate.",
  },
  {
    field: "category, summary, why_it_matters, scores, evidence_sufficiency, key_claims, limitations",
    owner: "Model → Pydantic",
    detail: "Validated against schema bounds; corrupt cache triggers re-inference.",
  },
  {
    field: "canonical_url, HN score/comments, timestamps, story ids, rank score, watermarks",
    owner: "Application",
    detail: "Never part of the model analysis schema.",
  },
] as const;

export type DataNode = {
  id: string;
  label: string;
  role: string;
};

export const dataFlowNodes: DataNode[] = [
  {
    id: "articles",
    label: "articles",
    role: "One row per canonical URL; text + extraction + optional HN fields",
  },
  {
    id: "analyses",
    label: "article_analyses",
    role: "Cached structured analyses keyed by article + content + model + config",
  },
  {
    id: "stories",
    label: "stories + story_articles",
    role: "Story shells and membership with link_reason",
  },
  {
    id: "processing",
    label: "article_processing_state / story_processing_state",
    role: "Hourly backlog: pending → failed/done (articles); pending/ready/failed/reported/skipped (stories)",
  },
  {
    id: "reports",
    label: "reports",
    role: "Persisted Markdown briefings with mode, as_of, window, status",
  },
  {
    id: "watermarks",
    label: "report_watermarks + story_report_state",
    role: "Per-mode publication watermark and per-(story, mode) last-reported state",
  },
];

export const dataFlowEdges = [
  "Collection upserts articles (+ article_sources sightings).",
  "Story sync links articles into stories (exact URL + conservative near-dupe).",
  "Hourly backlog enqueues analyses; cache hits skip Ollama.",
  "Report generation reads ranked eligible stories, persists reports, then may advance mode watermark.",
] as const;

export const schemaVersionNote =
  "Conceptual schema below mirrors storage.py. Current schema_version is 6. Labels are simplified for teaching — not a full DDL dump.";

export const rankingFormula = {
  expression:
    "0.35·significance + 0.25·relevance + 0.25·category_priority + 0.10·ai_signal + 0.05·hn_attention_capped",
  source: "qwennews/ranking.py · compute_rank_score_m2()",
  notes: [
    "significance / relevance come from the model (integers 1–5).",
    "category_priority, ai_signal, and hn_attention_capped are computed in Python.",
    "hn_attention_capped ≈ 1 + 1.2·log10(hn_score+1), clamped to [1, 3.5]; missing HN → 2.0.",
    "Low-priority categories (weather, sports, …) are capped further before blending.",
    "Diversity caps: max 3 per source, max 4 per category (apply_diversity).",
    "The model does not order the briefing — final rank is Python-only.",
  ],
} as const;

export const dedupeNotes = [
  {
    title: "Exact URL",
    body: "URLs are canonicalized (tracking params stripped). Upsert by id or canonical_url yields new / updated / duplicate. The same story on HN + RSS is one article with multiple source sightings.",
  },
  {
    title: "Conservative near-duplicates",
    body: "Story linking uses title/content Jaccard, distinctive entities, and version cues. Policy prefers false negatives. Broad topic tokens alone (including company names like openai/google/nvidia) are insufficient to merge.",
  },
  {
    title: "Same company ≠ same story",
    body: "There is no company/entity clustering pass. Two OpenAI product posts can remain separate stories when titles/bodies fail merge thresholds — intentional for an AI briefing.",
  },
  {
    title: "Update classes",
    body: "Story decisions: NEW_STORY, NEW_SOURCE_SAME_STORY, MEANINGFUL_UPDATE, UNCHANGED. HN score/comment churn alone stays UNCHANGED.",
  },
] as const;

export const reliabilityGuarantees = [
  {
    title: "Single-instance lock",
    application:
      "fcntl flock on a shared orchestrate.lock so hourly and daily never run Qwen concurrently. LockBusyError → lock_busy.",
    verified: "Unit tests cover busy / stale-PID steal paths.",
    notClaimed: "Does not prove a timer already fired on a given Mac.",
  },
  {
    title: "Bounded analysis + retryables",
    application:
      "Per-cycle analyze cap (default 20; env QWENNEWS_MAX_ANALYZE_PER_CYCLE). Failed article analyses can remain retryable; watermark stays frozen while backlog active > 0.",
    verified: "M3.1 backlog tests + orchestration outcome classifications.",
    notClaimed: "Public site explorer uses a teaching cap of 5 — not the production default.",
  },
  {
    title: "Persist before watermark",
    application:
      "report_persist_failed leaves watermarks unchanged. Advancement requires successful persist (and for hourly, drained backlog).",
    verified: "Orchestration / report tests assert non-advance on persist failure.",
    notClaimed: "Does not imply every operator machine has a successful live persist log published here.",
  },
  {
    title: "Missing Ollama",
    application:
      "ollama_unavailable / model-missing exits without advancing watermarks; hard mid-batch Ollama failure can stop further live inference in that cycle.",
    verified: "Mocked client failure tests in the Python suite.",
    notClaimed: "This static site never contacts Ollama.",
  },
  {
    title: "Read-only private dashboard API",
    application:
      "SQLite mode=ro + query_only; GET-only middleware; loopback bind. Status may probe Ollama read-only but does not start inference or control LaunchAgents.",
    verified: "API / readonly_store tests and architecture docs.",
    notClaimed: "Dashboard screenshots and live endpoints are not part of this public site.",
  },
  {
    title: "macOS launchd",
    application:
      "Opt-in LaunchAgents (hourly interval / daily calendar). Templates generated from packaging; RunAtLoad=false.",
    verified: "Generator/unit coverage for plist content; install is operator-driven.",
    notClaimed:
      "M4.2 recorded agents as not yet timer-verified. Loaded ≠ successful timer fire.",
  },
] as const;

export const schemaExpandables = [
  {
    id: "analysis-fields",
    title: "ArticleAnalysis fields",
    summary: "Pydantic model required keys and bounds",
    detail:
      "Required: article_id, category, summary, why_it_matters, relevance_score (1–5), significance_score (1–5), evidence_sufficiency, key_claims (≤8), limitations. additionalProperties false in JSON schema sent to Ollama format=.",
  },
  {
    id: "cache-key",
    title: "Analysis cache key",
    summary: "When inference is skipped",
    detail:
      "Unique on (article_id, content_hash, model_id, config_version). Unchanged article content with the same model/config reuses the prior analysis row — no new Ollama call.",
  },
  {
    id: "processing-status",
    title: "Processing status vocabulary",
    summary: "Hourly backlog states",
    detail:
      "Articles: pending | failed | done. Stories: pending | ready | failed | reported | skipped. Empty selection with ready stories can mark skipped so they do not block watermark drain.",
  },
] as const;

export const doNotClaim = [
  "LaunchAgent timer success from install/loaded alone",
  "Cloud inference, API-key LLM path, or fine-tuning",
  "Embedding/semantic clustering or automatic same-company merges",
  "Model-owned ranking or model-authored report layout",
  "Model-owned URLs (schema has none; app owns links)",
  "Public site reading live SQLite or calling Ollama",
  "Dashboard mutating DB or controlling launchd",
] as const;
