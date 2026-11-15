import { StoryItem } from "@/components/StoryItem";
import { StateBanner } from "@/components/StateBanner";
import { fetchToday, getApiBase } from "@/lib/api";
import { formatWhen } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function TodayPage() {
  let data;
  let error: string | null = null;
  try {
    data = await fetchToday();
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load today";
  }

  if (error) {
    return (
      <>
        <h1 className="page-title">Today</h1>
        <StateBanner kind="error">
          Cannot reach the local API at {getApiBase()}. Start the dashboard with{" "}
          <code>python -m qwennews dashboard</code> (or{" "}
          <code>python scripts/run_dashboard.py</code>). ({error})
        </StateBanner>
      </>
    );
  }

  assertData(data);

  return (
    <>
      <h1 className="page-title">Today</h1>
      <p className="lede">
        Latest briefing from your local QwenNews store — summaries and links only from
        saved analyses, never invented copy.
      </p>

      {data.source === "fallback" || data.source === "empty" ? (
        <StateBanner kind="warn">{data.fallback_reason}</StateBanner>
      ) : null}

      {data.report ? (
        <StateBanner>
          {data.report.mode?.toUpperCase()} briefing · generated{" "}
          {formatWhen(data.report.as_of || data.report.created_at)} (report time) ·{" "}
          {data.report.story_count} listed in report. Article publication times appear on each
          story card when the feed provided them.
        </StateBanner>
      ) : (
        <StateBanner kind="warn">
          No reports available yet. Run{" "}
          <code>python -m qwennews run-daily</code> or wait for the daily LaunchAgent.
        </StateBanner>
      )}

      {data.stories.length === 0 ? (
        <p className="empty">No developing stories with stored analyses yet.</p>
      ) : (
        <section className="story-list" aria-label="Important stories">
          {data.stories.map((story) => (
            <StoryItem key={story.id} story={story} />
          ))}
        </section>
      )}
    </>
  );
}

function assertData(
  data: Awaited<ReturnType<typeof fetchToday>> | undefined,
): asserts data is Awaited<ReturnType<typeof fetchToday>> {
  if (!data) throw new Error("missing");
}
