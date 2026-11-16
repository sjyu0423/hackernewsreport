import type { Metadata } from "next";
import Link from "next/link";
import { BacklogExplorer } from "@/components/BacklogExplorer";
import { BenchmarkChart } from "@/components/BenchmarkChart";
import { PageHero } from "@/components/PageHero";
import {
  githubDocLinks,
  m1BenchmarkMeta,
  m3CycleCaveat,
  m3ObservedCycles,
  testSuiteSnapshots,
} from "@/lib/benchmarks";
import { failureScenarios, launchAgentHonesty } from "@/lib/failures";
import {
  engineeringTradeoffs,
  evaluationCaveat,
} from "@/lib/tradeoffs";

export const metadata: Metadata = {
  title: "Engineering",
  description:
    "Verified QwenNews engineering evidence: M1 benchmarks, caching and orchestration observations, backlog simulation, failure policy, and design tradeoffs.",
  alternates: { canonical: "/engineering/" },
  openGraph: {
    title: "Engineering · QwenNews",
    description:
      "Verified QwenNews engineering evidence: M1 benchmarks, caching and orchestration observations, backlog simulation, failure policy, and design tradeoffs.",
    url: "/engineering/",
  },
};

export default function EngineeringPage() {
  return (
    <div className="shell space-y-16 pb-20">
      <PageHero
        eyebrow="Engineering"
        title="Evidence, reliability, and tradeoffs"
        description="Benchmarks and failure behavior drawn from milestone documentation and verification sessions. Charts and explorers explain decisions — they are not live production telemetry."
      >
        <div className="flex flex-wrap gap-3">
          <a
            href={githubDocLinks.m1}
            className="btn-secondary no-underline"
            rel="noopener noreferrer"
            target="_blank"
          >
            M1 milestone docs
          </a>
          <Link href="/how-it-works/" className="btn-secondary no-underline">
            Architecture walkthrough
          </Link>
        </div>
      </PageHero>

      <BenchmarkChart />

      <section className="space-y-6" aria-labelledby="caching-heading">
        <div className="max-w-3xl">
          <h2 id="caching-heading" className="text-3xl sm:text-4xl">
            Caching and orchestration
          </h2>
          <p className="mt-3 text-muted">
            Per-article analysis caching means unchanged stories skip inference.
            Bounded concurrency and durable queues keep pending or failed work
            visible. Hourly and daily reports use separate watermarks so one
            cadence cannot silently consume the other.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {m3ObservedCycles.map((cycle) => (
            <article key={cycle.id} className="panel space-y-3 p-5 sm:p-6">
              <p className="eyebrow">{cycle.title}</p>
              <p className="font-display text-3xl text-paper">
                {cycle.durationSeconds}s
              </p>
              <p className="text-sm text-muted">
                {cycle.analyses === 0
                  ? "Zero analyses — cache/eligibility quiet path"
                  : `${cycle.analyses} analyses in one bounded cycle`}
              </p>
              <p className="text-sm leading-relaxed text-muted">{cycle.note}</p>
            </article>
          ))}
        </div>

        <p className="max-w-3xl text-sm leading-relaxed text-muted">
          {m3CycleCaveat} Primary narrative:{" "}
          <a
            href={githubDocLinks.m3}
            rel="noopener noreferrer"
            target="_blank"
          >
            docs/milestones/m3.md
          </a>
          .
        </p>
      </section>

      <BacklogExplorer />

      <section className="space-y-6" aria-labelledby="failure-heading">
        <div className="max-w-3xl">
          <h2 id="failure-heading" className="text-3xl sm:text-4xl">
            Failure policy
          </h2>
          <p className="mt-3 text-muted">
            Each scenario separates application behavior, automated tests, and
            what operators can observe. Public site copy never claims a
            timer-triggered LaunchAgent fire without independent evidence.
          </p>
        </div>

        <div className="space-y-4">
          {failureScenarios.map((scenario) => (
            <article key={scenario.id} className="panel space-y-4 p-5 sm:p-6">
              <h3 className="text-xl text-paper">{scenario.title}</h3>
              <dl className="grid gap-4 md:grid-cols-3">
                <div>
                  <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
                    Application
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-muted">
                    {scenario.application}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
                    Tests
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-muted">
                    {scenario.tests}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
                    Operations
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-muted">
                    {scenario.operations}
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>

        <p className="max-w-3xl rounded-2xl border border-warn/30 bg-warn/5 px-4 py-3 text-sm leading-relaxed text-muted">
          {launchAgentHonesty} See{" "}
          <a
            href={githubDocLinks.m4_2}
            rel="noopener noreferrer"
            target="_blank"
          >
            M4.2 notes
          </a>
          .
        </p>
      </section>

      <section className="space-y-6" aria-labelledby="tradeoffs-heading">
        <div className="max-w-3xl">
          <h2 id="tradeoffs-heading" className="text-3xl sm:text-4xl">
            Engineering tradeoffs
          </h2>
          <p className="mt-3 text-muted">{evaluationCaveat}</p>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {engineeringTradeoffs.map((item) => (
            <article key={item.id} className="panel space-y-3 p-5 sm:p-6">
              <h3 className="text-xl text-paper">{item.title}</h3>
              <p className="text-sm leading-relaxed text-muted">
                <span className="font-medium text-ok">Gain.</span> {item.gain}
              </p>
              <p className="text-sm leading-relaxed text-muted">
                <span className="font-medium text-warn">Cost.</span> {item.cost}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="space-y-6" aria-labelledby="evidence-heading">
        <div className="max-w-3xl">
          <h2 id="evidence-heading" className="text-3xl sm:text-4xl">
            Technical evidence snapshots
          </h2>
          <p className="mt-3 text-muted">
            Test counts are dated milestone snapshots, not live CI counters on
            this static site. Model and wall-time figures above come from the{" "}
            {m1BenchmarkMeta.date} M1 live benchmark (
            {m1BenchmarkMeta.modelId}, {m1BenchmarkMeta.quantization}).
          </p>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-line">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">
              Historical test suite snapshots by milestone
            </caption>
            <thead className="bg-ink-soft/80 text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">
                  Milestone
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Date
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Count
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Kind
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Provenance
                </th>
              </tr>
            </thead>
            <tbody>
              {testSuiteSnapshots.map((row) => (
                <tr key={row.milestone} className="border-t border-line/80">
                  <th scope="row" className="px-4 py-3 font-medium text-paper">
                    {row.milestone}
                  </th>
                  <td className="px-4 py-3 font-mono text-muted">{row.date}</td>
                  <td className="px-4 py-3 font-mono text-paper">{row.count}</td>
                  <td className="px-4 py-3 text-muted">{row.kind}</td>
                  <td className="px-4 py-3 text-muted">{row.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <ul className="space-y-2 text-sm text-muted">
          {m1BenchmarkMeta.sources.map((source) => (
            <li key={source}>Source note: {source}</li>
          ))}
          <li>
            Architecture overview:{" "}
            <a
              href={githubDocLinks.architecture}
              rel="noopener noreferrer"
              target="_blank"
            >
              docs/architecture.md
            </a>
          </li>
        </ul>
      </section>
    </div>
  );
}
