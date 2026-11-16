import { systemBoundaries } from "@/lib/architecture";

export function SystemBoundaries() {
  return (
    <section className="space-y-6" aria-labelledby="boundaries-heading">
      <div className="max-w-3xl">
        <h2 id="boundaries-heading" className="text-3xl sm:text-4xl">
          System boundaries
        </h2>
        <p className="mt-3 text-muted">
          Three surfaces, three jobs. The public website explains and
          demonstrates; it does not operate the live analyst.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {systemBoundaries.map((boundary) => (
          <article
            key={boundary.id}
            className="rounded-2xl border border-line/80 bg-ink-elevated/55 p-5"
          >
            <h3 className="text-xl">{boundary.title}</h3>
            <p className="mt-2 font-mono text-xs uppercase tracking-[0.12em] text-violet">
              {boundary.runs}
            </p>
            <div className="mt-4 space-y-3 text-sm">
              <div>
                <p className="font-medium text-paper">Does</p>
                <ul className="mt-2 space-y-1 text-muted">
                  {boundary.does.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-medium text-paper">Does not</p>
                <ul className="mt-2 space-y-1 text-muted">
                  {boundary.doesNot.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
