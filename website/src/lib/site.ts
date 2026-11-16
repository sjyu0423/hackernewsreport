export const siteConfig = {
  name: "QwenNews",
  tagline: "Your own AI news analyst.",
  supportLine: "Running locally. Reading continuously. Reporting what matters.",
  description:
    "QwenNews is a local AI news reporting system: Hacker News and AI/tech RSS ingestion, SQLite story memory, pretrained Qwen3 4B analysis via Ollama (not trained or fine-tuned here), and hourly/daily briefings on macOS — with a separate public project website.",
  shortDescription:
    "Local AI news reporting with pretrained Qwen3 4B via Ollama, SQLite, and macOS automation. Public project site — not the private live dashboard.",
  githubUrl: "https://github.com/sjyu0423/hackernewsreport",
} as const;

export type NavItem = {
  href: string;
  label: string;
  description: string;
};

export const primaryNav: NavItem[] = [
  {
    href: "/",
    label: "Home",
    description: "Product overview",
  },
  {
    href: "/demo/",
    label: "Demo",
    description: "Interactive news briefing",
  },
  {
    href: "/how-it-works/",
    label: "How It Works",
    description: "Architecture explanation",
  },
  {
    href: "/engineering/",
    label: "Engineering",
    description: "Benchmarks and design decisions",
  },
  {
    href: "/under-the-hood/",
    label: "Under the Hood",
    description: "Optional technical details",
  },
];

export const stackRoles = [
  {
    name: "Qwen3 4B",
    role: "Language model",
    detail:
      "Pretrained model used for structured article analysis. Not trained or fine-tuned by this project.",
  },
  {
    name: "Python",
    role: "Orchestration",
    detail:
      "Ingestion, ranking, story memory, report generation, CLI, and the read-only dashboard API.",
  },
  {
    name: "SQLite",
    role: "Persistent news memory",
    detail:
      "Articles, analyses, story links, watermarks, and orchestration history live in a local database.",
  },
  {
    name: "Ollama",
    role: "Local inference runtime",
    detail:
      "Serves Qwen3 4B on the machine. No cloud inference fallback in the product path.",
  },
  {
    name: "macOS launchd",
    role: "Scheduler",
    detail:
      "Optional LaunchAgents run hourly and daily pipelines. Installation is opt-in.",
  },
] as const;

export const homePipeline = [
  {
    step: "01",
    title: "Collect",
    body: "Python gathers stories from five public sources and normalizes them.",
  },
  {
    step: "02",
    title: "Remember",
    body: "SQLite keeps story history and prior reports so updates can be recognized.",
  },
  {
    step: "03",
    title: "Analyze",
    body: "Pretrained Qwen3 4B runs locally through Ollama and returns structured summaries.",
  },
  {
    step: "04",
    title: "Report",
    body: "Hourly and daily briefings highlight developments that matter.",
  },
] as const;

export const publicFixtureNote =
  "Demo content uses an explicitly selected, sanitized static JSON snapshot of real local analyses. This site never connects to Ollama, FastAPI, or local SQLite at runtime.";
