type ComingSoonPanelProps = {
  milestone: string;
  title: string;
  summary: string;
  planned: string[];
};

export function ComingSoonPanel({
  milestone,
  title,
  summary,
  planned,
}: ComingSoonPanelProps) {
  return (
    <section
      className="panel fade-rise-delay p-6 sm:p-8"
      aria-labelledby={`${milestone}-heading`}
    >
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <span className="status-chip">
          <span className="status-dot" aria-hidden="true" />
          Planned · {milestone}
        </span>
      </div>
      <h2 id={`${milestone}-heading`} className="text-2xl sm:text-3xl">
        {title}
      </h2>
      <p className="mt-3 max-w-prose text-muted">{summary}</p>
      <ul className="mt-6 grid gap-3 sm:grid-cols-2">
        {planned.map((item) => (
          <li
            key={item}
            className="rounded-xl border border-line/80 bg-ink-soft/50 px-4 py-3 text-sm text-paper/90"
          >
            {item}
          </li>
        ))}
      </ul>
      <p className="mt-6 text-sm text-muted" role="status">
        Content architecture only in W0. Interactive demos and measured
        engineering evidence arrive in later website milestones.
      </p>
    </section>
  );
}
