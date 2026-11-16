import type { Metadata } from "next";
import Link from "next/link";
import { BriefingPreview } from "@/components/BriefingPreview";
import {
  demoSnapshot,
  featuredStories,
} from "@/lib/demo";
import { engineeringEvidence } from "@/lib/evidence";
import { routeMeta } from "@/lib/seo";
import {
  homePipeline,
  publicFixtureNote,
  siteConfig,
} from "@/lib/site";

export const metadata: Metadata = {
  description: routeMeta.home.description,
  alternates: { canonical: "/" },
  openGraph: {
    title: `${siteConfig.name} — ${siteConfig.tagline}`,
    description: routeMeta.home.description,
    url: "/",
  },
};

export default function HomePage() {
  const previewStories = featuredStories(3);

  return (
    <div className="shell pb-20">
      <section className="fade-rise grid gap-10 border-b border-line/70 pb-14 pt-14 lg:grid-cols-[minmax(0,1.15fr)_minmax(20rem,0.95fr)] lg:items-start lg:gap-12 lg:pb-16 lg:pt-20">
        <div className="space-y-6">
          <p className="eyebrow">Local AI news reporting</p>
          <h1 className="max-w-3xl text-5xl leading-[1.05] sm:text-6xl lg:text-[4.35rem]">
            {siteConfig.tagline}
          </h1>
          <p className="max-w-2xl font-display text-2xl leading-snug text-paper/90 sm:text-3xl">
            {siteConfig.supportLine}
          </p>
          <p className="lede">
            Pretrained Qwen3 4B runs locally through Ollama — this project does
            not train or fine-tune the model. Python collects and processes news
            from five sources. SQLite tracks story history and prior reports.
            Hourly and daily briefings highlight important developments.
          </p>
          <p className="max-w-2xl text-sm leading-relaxed text-muted">
            This public website is a static demonstration — not the private live
            dashboard. {publicFixtureNote}
          </p>
          <div className="flex flex-wrap gap-3 pt-1">
            <Link href="/demo/" className="btn-primary no-underline">
              Try the interactive demo
            </Link>
            <Link href="/how-it-works/" className="btn-secondary no-underline">
              How it works
            </Link>
            <a
              href={siteConfig.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary no-underline"
            >
              GitHub
            </a>
          </div>
        </div>

        <BriefingPreview
          stories={previewStories}
          snapshotId={demoSnapshot.snapshot_id}
          recordedAt={demoSnapshot.recorded_at}
        />
      </section>

      <section className="grid gap-8 border-b border-line/70 py-14 lg:grid-cols-[0.85fr_1.15fr]">
        <div>
          <p className="eyebrow">How it works</p>
          <h2 className="mt-3 text-3xl sm:text-4xl">A local reporting loop</h2>
          <p className="mt-3 max-w-md text-muted">
            Collect, remember, analyze, report — without cloud inference or
            model fine-tuning.
          </p>
          <Link
            href="/how-it-works/"
            className="mt-5 inline-flex min-h-11 items-center text-sm no-underline"
          >
            Full architecture explanation
          </Link>
        </div>
        <ol className="grid gap-3 sm:grid-cols-2">
          {homePipeline.map((item) => (
            <li
              key={item.step}
              className="rounded-2xl border border-line/80 bg-ink-elevated/55 p-5"
            >
              <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">
                {item.step}
              </p>
              <h3 className="mt-2 text-xl">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                {item.body}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-8 border-b border-line/70 py-14 lg:grid-cols-[0.85fr_1.15fr]">
        <div>
          <p className="eyebrow">Engineering evidence</p>
          <h2 className="mt-3 text-3xl sm:text-4xl">Measured, not invented</h2>
          <p className="mt-3 max-w-md text-muted">
            Figures below come from repository milestone notes and the M1 live
            benchmark JSON. Conditions remain visible on the Engineering page.
          </p>
          <Link
            href="/engineering/"
            className="mt-5 inline-flex min-h-11 items-center text-sm no-underline"
          >
            Benchmark details
          </Link>
        </div>
        <dl className="grid gap-3 sm:grid-cols-2">
          {engineeringEvidence.map((item) => (
            <div
              key={item.label}
              className="rounded-2xl border border-line/80 bg-ink-elevated/55 p-5"
            >
              <dt className="font-mono text-xs uppercase tracking-[0.14em] text-violet">
                {item.label}
              </dt>
              <dd className="mt-2 font-display text-2xl text-paper">
                {item.value}
              </dd>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                {item.detail}
              </p>
            </div>
          ))}
        </dl>
      </section>

      <section className="panel mt-14 grid gap-6 p-6 sm:p-8 lg:grid-cols-[1.25fr_0.75fr] lg:items-center">
        <div>
          <p className="eyebrow">Featured demo</p>
          <h2 className="mt-3 text-3xl sm:text-4xl">
            Explore a recorded briefing
          </h2>
          <p className="mt-3 max-w-prose text-muted">
            Filter and expand eight curated stories with original source links.
            Every card is grounded in a real local analysis — clearly labeled as
            a fixed snapshot.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link href="/demo/" className="btn-primary no-underline">
            Open the demo
          </Link>
          <Link href="/under-the-hood/" className="btn-secondary no-underline">
            Technical notes
          </Link>
        </div>
      </section>
    </div>
  );
}
