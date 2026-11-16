import { demoSnapshot, getDemoStories, type DemoStory } from "@/lib/demo";

export type ArchitectureStageId =
  | "collect"
  | "store"
  | "analyze"
  | "rank"
  | "publish";

export type ArchitectureStage = {
  id: ArchitectureStageId;
  step: string;
  title: string;
  shortLabel: string;
  summary: string;
  owner: "python" | "model" | "mixed";
  ownerLabel: string;
  inputs: string[];
  process: string[];
  outputs: string[];
  why: string;
  example: string;
};

export const architectureStages: ArchitectureStage[] = [
  {
    id: "collect",
    step: "01",
    title: "Collect",
    shortLabel: "Collect",
    summary:
      "Python adapters pull public Hacker News items and AI/tech RSS feeds, then normalize them into a shared article model.",
    owner: "python",
    ownerLabel: "Deterministic Python",
    inputs: [
      "Hacker News Firebase API story listings",
      "Verified RSS/Atom feeds (OpenAI, DeepMind, Hugging Face, TechCrunch AI)",
    ],
    process: [
      "Fetch with size limits, retries, robots.txt checks, and SSRF-safe redirects",
      "Canonicalize URLs and strip tracking parameters",
      "Optionally extract article text when allowed",
    ],
    outputs: [
      "Normalized article candidates with title, URLs, timestamps, and source sightings",
      "Collection-run metrics for later status inspection",
    ],
    why: "Reliable ingestion has to be deterministic and safety-bounded before any model call happens.",
    example:
      "A DeepMind blog post arrives from RSS with a public URL and publish time — still just structured metadata at this stage.",
  },
  {
    id: "store",
    step: "02",
    title: "Store & Deduplicate",
    shortLabel: "Store",
    summary:
      "SQLite keeps durable news memory: one article row per canonical URL, plus conservative story grouping across sightings.",
    owner: "python",
    ownerLabel: "Deterministic Python + SQLite",
    inputs: [
      "Normalized article candidates from collection",
      "Existing article and story rows in SQLite",
    ],
    process: [
      "Upsert by canonical URL so repeats do not create duplicate article rows",
      "Record source sightings (HN and RSS can point at the same article)",
      "Link near-duplicates conservatively into developing stories",
    ],
    outputs: [
      "Persistent articles, source links, and story memory",
      "Update classifications such as NEW_STORY or UNCHANGED",
    ],
    why: "Without memory, every hourly run would treat familiar stories as brand new.",
    example:
      "The same canonical DeepMind URL seen again updates last-seen time instead of inserting a second article.",
  },
  {
    id: "analyze",
    step: "03",
    title: "Analyze Locally",
    shortLabel: "Analyze",
    summary:
      "Ollama serves pretrained Qwen3 4B locally. Python prompts one article at a time and validates structured JSON with Pydantic.",
    owner: "mixed",
    ownerLabel: "Model inference + Python validation",
    inputs: [
      "Stored article text or thin-content hints",
      "Local Ollama endpoint with model id qwen3:4b",
    ],
    process: [
      "Call Ollama’s local chat API with concurrency=1 (no cloud fallback)",
      "Require schema fields: summary, why_it_matters, scores, evidence_sufficiency",
      "Cache by article + content hash + model + config version",
    ],
    outputs: [
      "Validated ArticleAnalysis records",
      "Evidence labels (sufficient / partial / insufficient)",
    ],
    why: "The model writes grounded summaries; Python owns prompting, validation, caching, and failure handling.",
    example:
      "Qwen returns a structured analysis for “Introducing Gemini 4 Hydrogen”; invalid JSON is rejected rather than published.",
  },
  {
    id: "rank",
    step: "04",
    title: "Rank & Track",
    shortLabel: "Rank",
    summary:
      "Deterministic ranking blends significance, relevance, category priority, mild AI signal, and capped HN attention — never treating popularity as truth.",
    owner: "python",
    ownerLabel: "Deterministic Python",
    inputs: [
      "Validated analyses and story memory",
      "Mode-specific report state (hourly vs daily)",
    ],
    process: [
      "Score with the documented M2 blend and diversity limits",
      "Detect novelty / meaningful updates vs unchanged churn",
      "Keep independent watermarks and story_report_state per mode",
    ],
    outputs: [
      "Ordered candidates for briefing inclusion",
      "Durable processing state so reruns are crash-safe",
    ],
    why: "Briefings need repeatable selection rules, not opaque model-chosen rankings.",
    example:
      "An AI-model launch with strong evidence can outrank a high-HN non-AI item once category priors apply.",
  },
  {
    id: "publish",
    step: "05",
    title: "Publish",
    shortLabel: "Publish",
    summary:
      "Python renders Markdown hourly deltas and daily briefings. Optional macOS launchd agents schedule the orchestration loop.",
    owner: "python",
    ownerLabel: "Deterministic Python + launchd",
    inputs: [
      "Ranked story views and report templates",
      "Orchestration triggers from CLI or LaunchAgents",
    ],
    process: [
      "Write persisted reports with mode, window, and status metadata",
      "Advance watermarks only on successful drained outcomes",
      "Single-instance lock so hourly and daily never run Qwen concurrently",
    ],
    outputs: [
      "Hourly delta reports and daily digests",
      "Local read-only dashboard views over SQLite mode=ro",
    ],
    why: "Publishing and scheduling stay outside the model so operators can audit what shipped and when.",
    example:
      "A LaunchAgent may trigger run-hourly; the private dashboard only reads the resulting report — it never calls Ollama.",
  },
];

export const architectureStageIds = architectureStages.map((stage) => stage.id);

export function getStage(id: ArchitectureStageId): ArchitectureStage {
  const stage = architectureStages.find((item) => item.id === id);
  if (!stage) {
    throw new Error(`Unknown architecture stage: ${id}`);
  }
  return stage;
}

export function nextStageId(
  id: ArchitectureStageId,
  delta: 1 | -1,
): ArchitectureStageId {
  const index = architectureStageIds.indexOf(id);
  const next =
    (index + delta + architectureStageIds.length) % architectureStageIds.length;
  return architectureStageIds[next];
}

export type EngineeringDecision = {
  id: string;
  title: string;
  summary: string;
  detail: string;
  source: string;
};

export const engineeringDecisions: EngineeringDecision[] = [
  {
    id: "local-inference",
    title: "Local inference instead of a cloud model",
    summary:
      "All analysis goes through local Ollama with qwen3:4b. There is no cloud inference fallback in the product path.",
    detail:
      "Keeping the model on-machine preserves privacy for collected article text, removes API-key dependency for inference, and makes latency/throughput measurable on the same hardware that runs scheduling.",
    source: "docs/milestones/m1.md, docs/architecture.md",
  },
  {
    id: "sqlite",
    title: "SQLite for small-scale persistent state",
    summary:
      "Articles, analyses, stories, watermarks, and orchestration history live in one local SQLite database.",
    detail:
      "For a single-operator Mac deployment, SQLite gives durable joins and migrations without operating a separate database service. The private dashboard opens the same DB with mode=ro.",
    source: "docs/architecture.md, M4/M4.2 notes",
  },
  {
    id: "near-dupes",
    title: "Conservative near-duplicate detection",
    summary:
      "Story linking prefers precision over aggressive clustering so unrelated articles are not forced together.",
    detail:
      "M2 classifies NEW_STORY / NEW_SOURCE_SAME_STORY / MEANINGFUL_UPDATE / UNCHANGED. HN score-only changes stay UNCHANGED. Embedding-based clustering remains deferred.",
    source: "docs/architecture.md, docs/milestones/m2.md",
  },
  {
    id: "deterministic-reports",
    title: "Deterministic report formatting",
    summary:
      "Ranking and Markdown templates are code-defined. The model does not choose the final briefing layout.",
    detail:
      "M2 rank = 0.35*significance + 0.25*relevance + 0.25*category_priority + 0.10*ai_signal + 0.05*hn_attention_capped, with diversity caps. Popularity is never treated as truth.",
    source: "docs/architecture.md ranking section",
  },
  {
    id: "bounded-inference",
    title: "Bounded inference and caching",
    summary:
      "Analysis runs with concurrency=1 and caches validated results by content hash, model, and config version.",
    detail:
      "Bounded concurrency protects a small local machine. Unchanged article content with the same model/config reuses the cached analysis (article_id + content_hash + model_id + config_version). Measured quiet vs active cycle times are different workloads — see Engineering — not a controlled A/B speedup claim.",
    source: "docs/milestones/m1.md, docs/milestones/m3.md, website Engineering page",
  },
  {
    id: "watermarks",
    title: "Durable queues and watermarks",
    summary:
      "Hourly and daily modes keep independent report state. Watermarks advance only on safe drained outcomes.",
    detail:
      "Orchestration outcomes such as collect_failed or ollama_unavailable leave watermarks unchanged. backlog_remaining also refuses to advance so pending work is not skipped.",
    source: "docs/architecture.md orchestration failure policy",
  },
  {
    id: "readonly-api",
    title: "Read-only private dashboard API",
    summary:
      "The private dashboard FastAPI app is localhost-bound and GET-only over SQLite mode=ro.",
    detail:
      "It never triggers inference or LaunchAgent changes. That keeps operator browsing from mutating production memory or competing with scheduled analysis locks.",
    source: "docs/architecture.md M4, docs/milestones/m4.md",
  },
];

export type SystemBoundary = {
  id: string;
  title: string;
  runs: string;
  does: string[];
  doesNot: string[];
};

export const systemBoundaries: SystemBoundary[] = [
  {
    id: "local-app",
    title: "QwenNews local application",
    runs: "Python package + optional LaunchAgents + local Ollama",
    does: [
      "Collect, store, analyze, rank, and publish reports",
      "Own SQLite production memory and orchestration locks",
    ],
    doesNot: [
      "Serve this public website",
      "Expose a public write API",
    ],
  },
  {
    id: "public-site",
    title: "Static public website",
    runs: "Next.js static export (GitHub Pages compatible)",
    does: [
      "Explain the system and demonstrate fixed analysis snapshots",
      "Filter/sort curated JSON entirely in the browser",
    ],
    doesNot: [
      "Call Ollama or FastAPI",
      "Read live SQLite or private logs",
    ],
  },
  {
    id: "private-dashboard",
    title: "Existing private dashboard",
    runs: "Localhost FastAPI (mode=ro) + Next.js UI",
    does: [
      "Browse live reports/status on the operator machine",
      "Render sanitized Markdown from the local DB",
    ],
    doesNot: [
      "Replace this public marketing/demo site",
      "Start model inference from page views",
    ],
  },
];

export type JourneyStep = {
  id: string;
  title: string;
  kind: "actual" | "schematic";
  body: string;
  facts: Array<{ label: string; value: string }>;
};

export type ArticleJourney = {
  story: DemoStory;
  snapshotId: string;
  recordedAt: string;
  steps: JourneyStep[];
};

/** Prefer a DeepMind AI launch from the curated W1 snapshot for the walkthrough. */
export function getJourneyStory(): DemoStory {
  const stories = getDemoStories();
  return (
    stories.find((story) => story.id === "demo-01") ??
    stories[0]
  );
}

export function buildArticleJourney(story: DemoStory = getJourneyStory()): ArticleJourney {
  const categoryPriority =
    story.category.toLowerCase() === "ai models" ? 5.0 : null;

  return {
    story,
    snapshotId: demoSnapshot.snapshot_id,
    recordedAt: demoSnapshot.recorded_at,
    steps: [
      {
        id: "source",
        title: "1. Original source article",
        kind: "actual",
        body: "Public source URL and headline from the curated W1 snapshot (ingested via the DeepMind RSS adapter in the local app).",
        facts: [
          { label: "Headline", value: story.headline },
          { label: "Source", value: story.source_name },
          { label: "URL", value: story.source_url },
          {
            label: "Published",
            value: story.published_at ?? "Unknown",
          },
        ],
      },
      {
        id: "normalized",
        title: "2. Normalized article metadata",
        kind: "schematic",
        body: "Schematic view of the shared article model after Python normalization. Field names match the application model; private DB ids are not published.",
        facts: [
          { label: "canonical_url", value: story.source_url },
          { label: "title", value: story.headline },
          {
            label: "published_at",
            value: story.published_at ?? "null",
          },
          {
            label: "source sighting",
            value: `${story.source_name} (RSS)`,
          },
          {
            label: "public fixture id",
            value: story.id,
          },
        ],
      },
      {
        id: "analysis",
        title: "3. Stored analysis output",
        kind: "actual",
        body: "Actual Qwen3 4B structured fields from the W1 snapshot — the same text shown in the public demo.",
        facts: [
          { label: "Model", value: story.model_id },
          { label: "Category", value: story.category },
          {
            label: "Scores",
            value: `relevance ${story.relevance_score}/5 · significance ${story.significance_score}/5`,
          },
          {
            label: "Evidence",
            value: story.evidence_sufficiency,
          },
          { label: "Summary", value: story.summary },
          { label: "Why it matters", value: story.why_it_matters },
        ],
      },
      {
        id: "ranking",
        title: "4. Story ranking / selection",
        kind: "schematic",
        body: "Schematic application of the documented M2 ranking blend using this article’s actual scores plus the documented AI Models category priority. Exact HN attention / ai_signal components are not exported in the public fixture, so the numeric blend below is illustrative.",
        facts: [
          {
            label: "Actual scores used",
            value: `significance=${story.significance_score}, relevance=${story.relevance_score}`,
          },
          {
            label: "Documented category prior",
            value:
              categoryPriority === null
                ? `Lookup for “${story.category}” not hard-coded here`
                : `AI Models → ${categoryPriority}`,
          },
          {
            label: "Documented formula",
            value:
              "0.35*sig + 0.25*rel + 0.25*category + 0.10*ai_signal + 0.05*hn_capped",
          },
          {
            label: "Illustrative partial blend",
            value:
              categoryPriority === null
                ? "n/a"
                : `0.35*${story.significance_score} + 0.25*${story.relevance_score} + 0.25*${categoryPriority} = ${(
                    0.35 * story.significance_score +
                    0.25 * story.relevance_score +
                    0.25 * categoryPriority
                  ).toFixed(2)} (ai_signal/HN terms omitted → schematic)`,
          },
        ],
      },
      {
        id: "briefing",
        title: "5. Final briefing presentation",
        kind: "actual",
        body: "On this public site, the article appears as a fixed demo card with original source attribution. In the local app, the same analysis can be rendered into Markdown hourly/daily reports for the private dashboard.",
        facts: [
          {
            label: "Public demo surface",
            value: `/demo/ card for ${story.id}`,
          },
          {
            label: "Snapshot",
            value: `${demoSnapshot.snapshot_id} · not live inference`,
          },
          {
            label: "Private app counterpart",
            value:
              "Markdown report sections + localhost dashboard (not this website)",
          },
        ],
      },
    ],
  };
}
