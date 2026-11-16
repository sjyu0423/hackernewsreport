import Link from "next/link";
import { publicFixtureNote, siteConfig, stackRoles } from "@/lib/site";

const capabilities = [
  "Hacker News and AI/tech RSS ingestion into a shared article model",
  "SQLite story history with conservative near-duplicate linking",
  "Local Qwen3 4B analysis through Ollama with structured summaries",
  "Significance scoring, ranking, and hourly/daily Markdown reports",
  "Optional macOS LaunchAgent scheduling and a private localhost dashboard",
] as const;

export default function HomePage() {
  return (
    <div className="shell pb-20">
      <section className="fade-rise grid gap-10 border-b border-line/70 pb-14 pt-14 lg:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.85fr)] lg:items-end lg:pb-16 lg:pt-20">
        <div className="space-y-6">
          <p className="eyebrow">Local AI news reporting</p>
          <h1 className="max-w-3xl text-5xl leading-[1.05] sm:text-6xl lg:text-[4.25rem]">
            {siteConfig.name}
          </h1>
          <p className="max-w-2xl font-display text-2xl leading-snug text-paper/90 sm:text-3xl">
            {siteConfig.tagline}
          </p>
          <p className="lede">
            A Mac-local reporting system that collects public tech/AI news,
            remembers developing stories in SQLite, and drafts briefings with a
            pretrained Qwen3 4B model — without cloud inference or model
            fine-tuning.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link href="/demo/" className="btn-primary no-underline">
              Explore the demo
            </Link>
            <Link href="/how-it-works/" className="btn-secondary no-underline">
              How it works
            </Link>
          </div>
        </div>

        <aside className="panel fade-rise-delay space-y-4 p-5 sm:p-6">
          <p className="eyebrow">Site scope</p>
          <p className="text-sm leading-relaxed text-muted">
            This is the <strong className="font-medium text-paper">public</strong>{" "}
            static project website. It is not the private Next.js dashboard and
            does not talk to your local FastAPI, Ollama, or SQLite databases.
          </p>
          <p className="text-sm leading-relaxed text-muted">{publicFixtureNote}</p>
        </aside>
      </section>

      <section className="fade-rise-delay grid gap-8 py-14 lg:grid-cols-[0.9fr_1.1fr]">
        <div>
          <h2 className="text-3xl sm:text-4xl">What exists today</h2>
          <p className="mt-3 max-w-md text-muted">
            Verified from the repository milestones M0–M4.2. No invented
            benchmarks or live demo claims.
          </p>
        </div>
        <ul className="space-y-3">
          {capabilities.map((item) => (
            <li
              key={item}
              className="rounded-xl border border-line/80 bg-ink-elevated/50 px-4 py-3 text-sm leading-relaxed text-paper/90"
            >
              {item}
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-6 border-t border-line/70 py-14">
        <div className="max-w-2xl">
          <h2 className="text-3xl sm:text-4xl">Who does what</h2>
          <p className="mt-3 text-muted">
            Clear roles for the model, runtime, storage, orchestration, and
            scheduler — so reviewers can see the system boundaries.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {stackRoles.map((item) => (
            <article
              key={item.name}
              className="rounded-2xl border border-line/80 bg-ink-elevated/55 p-5"
            >
              <p className="font-mono text-xs uppercase tracking-[0.14em] text-violet">
                {item.role}
              </p>
              <h3 className="mt-2 text-xl">{item.name}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                {item.detail}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="panel grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
        <div>
          <h2 className="text-2xl sm:text-3xl">Next on this website</h2>
          <p className="mt-3 max-w-prose text-muted">
            W0 establishes routing, layout, navigation, and content architecture.
            Later milestones add an interactive briefing demo, deeper
            architecture narrative, measured engineering evidence, and optional
            under-the-hood detail.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link href="/engineering/" className="btn-secondary no-underline">
            Engineering
          </Link>
          <Link href="/under-the-hood/" className="btn-secondary no-underline">
            Under the Hood
          </Link>
        </div>
      </section>
    </div>
  );
}
