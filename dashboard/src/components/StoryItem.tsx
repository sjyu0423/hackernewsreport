import type { StoryCard } from "@/lib/types";
import { formatWhen, safeHref } from "@/lib/format";

export function StoryItem({
  story,
  showArticles = false,
}: {
  story: StoryCard;
  showArticles?: boolean;
}) {
  const primary = story.primary;
  const href = safeHref(primary?.canonical_url ?? null);
  const published = primary?.published_at;
  const discovered = primary?.discovered_at;
  return (
    <article className="story">
      <h2>{story.title}</h2>
      <div className="meta">
        {story.category ? <span className="pill">{story.category}</span> : null}
        <span>First seen {formatWhen(story.first_seen_at)}</span>
        <span>Story updated {formatWhen(story.last_seen_at)}</span>
        <span>{story.article_count} source{story.article_count === 1 ? "" : "s"}</span>
      </div>
      <div className="meta time-split" aria-label="Publication vs discovery">
        {published ? (
          <span>
            Article published <time dateTime={published}>{formatWhen(published)}</time>
          </span>
        ) : (
          <span>Article published — (not stored)</span>
        )}
        {discovered ? (
          <span>
            Ingested <time dateTime={discovered}>{formatWhen(discovered)}</time>
          </span>
        ) : null}
      </div>
      {primary?.sources ? (
        <p className="attribution">
          Source attribution: <strong>{primary.sources}</strong>
        </p>
      ) : (
        <p className="attribution muted">Source attribution unavailable.</p>
      )}
      {primary?.summary ? <p className="summary">{primary.summary}</p> : null}
      {primary?.why_it_matters ? (
        <p className="why">
          <strong>Why it matters.</strong> {primary.why_it_matters}
        </p>
      ) : null}
      {href ? (
        <p>
          <a className="source-link" href={href} rel="noopener noreferrer" target="_blank">
            Open original source
            {primary?.sources ? ` · ${primary.sources}` : ""}
          </a>
        </p>
      ) : (
        <p className="why">No safe source URL available for this story.</p>
      )}
      {showArticles && story.articles.length > 1 ? (
        <ul className="source-list">
          {story.articles.map((a) => {
            const link = safeHref(a.canonical_url);
            return (
              <li key={a.id}>
                {link ? (
                  <a href={link} rel="noopener noreferrer" target="_blank">
                    {a.title}
                  </a>
                ) : (
                  a.title
                )}
                {a.sources ? ` · ${a.sources}` : ""}
                {a.published_at ? ` · published ${formatWhen(a.published_at)}` : ""}
              </li>
            );
          })}
        </ul>
      ) : null}
    </article>
  );
}
