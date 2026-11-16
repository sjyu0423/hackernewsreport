export const siteConfig = {
  name: "QwenNews",
  tagline: "Your own AI news analyst, running locally.",
  description:
    "QwenNews is a local AI news reporting system: Hacker News and AI/tech RSS ingestion, SQLite story memory, Qwen3 4B analysis via Ollama, and hourly/daily briefings on macOS — with a separate public project website.",
  shortDescription:
    "Local AI news reporting with Qwen3 4B, Ollama, SQLite, and macOS automation. Public project site — not the private live dashboard.",
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

/** Safe public fixture path under /content/fixtures — never live DB. */
export const publicFixtureNote =
  "Demo content will use explicitly selected, sanitized static JSON fixtures. This site never connects to Ollama, FastAPI, or local SQLite at runtime.";
