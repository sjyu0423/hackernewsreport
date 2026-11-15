import { StoryItem } from "@/components/StoryItem";
import { StateBanner } from "@/components/StateBanner";
import { fetchStories, getApiBase } from "@/lib/api";
import type { StoryCard } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function StoriesPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string }>;
}) {
  const params = await searchParams;
  let stories: StoryCard[] = [];
  let error: string | null = null;
  try {
    stories = await fetchStories(50, params.category);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load stories";
  }

  return (
    <>
      <h1 className="page-title">Developing stories</h1>
      <p className="lede">
        M2 story memory groupings with first-seen / last-updated timestamps and every
        linked source article. No new model inference on this page.
      </p>
      {error ? (
        <StateBanner kind="error">
          API unavailable at {getApiBase()}: {error}
        </StateBanner>
      ) : null}
      {!error && stories.length === 0 ? (
        <p className="empty">No stories in memory yet.</p>
      ) : (
        <section className="story-list" aria-label="Developing stories">
          {stories.map((story) => (
            <StoryItem key={story.id} story={story} showArticles />
          ))}
        </section>
      )}
    </>
  );
}
