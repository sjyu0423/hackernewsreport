import snapshot from "../../content/fixtures/demo-briefing.snapshot.json";

export type EvidenceSufficiency = "sufficient" | "partial" | "insufficient";

export type DemoStory = {
  id: string;
  headline: string;
  summary: string;
  why_it_matters: string;
  category: string;
  source_url: string;
  source_name: string;
  published_at: string | null;
  relevance_score: number;
  significance_score: number;
  evidence_sufficiency: EvidenceSufficiency;
  limitations?: string | null;
  key_claims?: string[];
  model_id: string;
  disclaimer: string;
};

export type DemoBriefingSnapshot = {
  version: number;
  kind: string;
  generated_for: string;
  snapshot_id: string;
  recorded_at: string;
  model_id: string;
  model_quantization: string;
  disclaimer: string;
  selection_notes: string[];
  items: DemoStory[];
};

export type DemoSort = "significance" | "relevance" | "published";

export const demoSnapshot = snapshot as DemoBriefingSnapshot;

export function getDemoStories(): DemoStory[] {
  return demoSnapshot.items;
}

export function listCategories(stories: DemoStory[]): string[] {
  return Array.from(new Set(stories.map((story) => story.category))).sort((a, b) =>
    a.localeCompare(b),
  );
}

export function filterStories(
  stories: DemoStory[],
  category: string | "all",
): DemoStory[] {
  if (category === "all") {
    return [...stories];
  }
  return stories.filter((story) => story.category === category);
}

export function sortStories(stories: DemoStory[], sort: DemoSort): DemoStory[] {
  const copy = [...stories];
  copy.sort((a, b) => {
    if (sort === "significance") {
      return (
        b.significance_score - a.significance_score ||
        b.relevance_score - a.relevance_score ||
        a.headline.localeCompare(b.headline)
      );
    }
    if (sort === "relevance") {
      return (
        b.relevance_score - a.relevance_score ||
        b.significance_score - a.significance_score ||
        a.headline.localeCompare(b.headline)
      );
    }
    const aTime = a.published_at ? Date.parse(a.published_at) : 0;
    const bTime = b.published_at ? Date.parse(b.published_at) : 0;
    return bTime - aTime || a.headline.localeCompare(b.headline);
  });
  return copy;
}

export function filterAndSortStories(
  stories: DemoStory[],
  category: string | "all",
  sort: DemoSort,
): DemoStory[] {
  return sortStories(filterStories(stories, category), sort);
}

/** Only allow http(s) links for public source attribution. */
export function isSafePublicUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function safeSourceHref(url: string): string | null {
  return isSafePublicUrl(url) ? url : null;
}

export function featuredStories(limit = 3): DemoStory[] {
  return sortStories(getDemoStories(), "significance").slice(0, limit);
}
