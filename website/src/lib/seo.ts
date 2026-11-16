/**
 * Production publishing targets for the public static site.
 * Intended GitHub Pages project URL — do not treat as proof the site is live.
 *
 * SITE_URL is the public origin including the project path
 * (https://sjyu0423.github.io/hackernewsreport). NEXT_PUBLIC_BASE_PATH is a
 * separate Next.js routing prefix applied to asset hrefs. Do not concatenate
 * basePath again onto SITE_URL when building absolute canonical/sitemap/OG URLs.
 */
export const productionSiteUrl =
  "https://sjyu0423.github.io/hackernewsreport" as const;

export const productionBasePath = "/hackernewsreport" as const;

export const githubRepoUrl =
  "https://github.com/sjyu0423/hackernewsreport" as const;

/** Absolute site origin used for metadataBase / canonical / sitemap. */
export function resolveSiteUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "");
  if (fromEnv) return fromEnv;
  return productionSiteUrl;
}

/**
 * Build an absolute public URL from a site-root path (`/demo/`).
 * Paths are relative to SITE_URL — never prefix basePath a second time.
 */
export function absolutePublicUrl(routePath: string): string {
  const origin = resolveSiteUrl().replace(/\/$/, "");
  const path = routePath.startsWith("/") ? routePath : `/${routePath}`;
  return `${origin}${path}`;
}

export const openGraphImage = {
  path: "/og-share.jpg",
  alt: "QwenNews — Your own AI news analyst. Local Qwen3 4B public project site.",
  width: 1376,
  height: 768,
} as const;

export const routeMeta = {
  home: {
    title: undefined as string | undefined,
    description:
      "QwenNews is a local AI news reporting system: pretrained Qwen3 4B via Ollama, five public news sources, SQLite story memory, and macOS briefings — with a separate static public project site.",
  },
  demo: {
    title: "Demo",
    description:
      "Interactive QwenNews briefing demo powered by a fixed snapshot of real local Qwen3 4B analyses — not live inference.",
  },
  howItWorks: {
    title: "How It Works",
    description:
      "Interactive QwenNews architecture: collect, store, analyze locally with pretrained Qwen3 4B, rank deterministically, and publish via optional launchd — plus system boundaries.",
  },
  engineering: {
    title: "Engineering",
    description:
      "Verified QwenNews engineering evidence: M1 benchmarks, caching and orchestration observations, backlog simulation, failure policy, and design tradeoffs.",
  },
  underTheHood: {
    title: "Under the Hood",
    description:
      "Technical deep dive for QwenNews: local inference contracts, SQLite memory model, ranking and deduplication, and reliability guarantees — grounded in application source.",
  },
} as const;
