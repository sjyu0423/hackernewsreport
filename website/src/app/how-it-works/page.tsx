import type { Metadata } from "next";
import Link from "next/link";
import { ArchitectureFlow } from "@/components/ArchitectureFlow";
import { ArticleJourney } from "@/components/ArticleJourney";
import { DecisionList } from "@/components/DecisionList";
import { PageHero } from "@/components/PageHero";
import { SystemBoundaries } from "@/components/SystemBoundaries";
import { stackRoles } from "@/lib/site";

export const metadata: Metadata = {
  title: "How It Works",
  description:
    "Interactive QwenNews architecture: collect, store, analyze locally with pretrained Qwen3 4B, rank deterministically, and publish via optional launchd — plus system boundaries.",
  alternates: { canonical: "/how-it-works/" },
  openGraph: {
    title: "How It Works · QwenNews",
    description:
      "Interactive QwenNews architecture: collect, store, analyze locally with pretrained Qwen3 4B, rank deterministically, and publish via optional launchd — plus system boundaries.",
    url: "/how-it-works/",
  },
};

export default function HowItWorksPage() {
  return (
    <div className="shell space-y-16 pb-20">
      <PageHero
        eyebrow="How It Works"
        title="How QwenNews turns public news into local briefings"
        description="Python orchestrates collection, memory, ranking, and publishing. A pretrained Qwen3 4B model — served locally by Ollama — only handles structured article analysis."
      >
        <p className="status-chip" role="status">
          <span className="status-dot" aria-hidden="true" />
          Static explanation · not live inference
        </p>
      </PageHero>

      <ArchitectureFlow />

      <section className="space-y-4">
        <h2 className="text-3xl">Who does what</h2>
        <p className="max-w-3xl text-muted">
          Keep the model and the orchestration system distinct: Qwen writes
          grounded summaries; Python decides what to fetch, store, rank, cache,
          and publish.
        </p>
        <div className="overflow-x-auto rounded-2xl border border-line">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">
              Roles of Qwen3 4B, Python, SQLite, Ollama, and launchd
            </caption>
            <thead className="bg-ink-soft/80 text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">
                  Component
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Role
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Notes
                </th>
              </tr>
            </thead>
            <tbody>
              {stackRoles.map((role) => (
                <tr key={role.name} className="border-t border-line/80">
                  <th scope="row" className="px-4 py-3 font-medium text-paper">
                    {role.name}
                  </th>
                  <td className="px-4 py-3 text-muted">{role.role}</td>
                  <td className="px-4 py-3 text-muted">{role.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <ArticleJourney />
      <DecisionList />
      <SystemBoundaries />

      <section className="panel grid gap-5 p-6 sm:p-8 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
        <div>
          <h2 className="text-2xl sm:text-3xl">See the analyses themselves</h2>
          <p className="mt-3 max-w-prose text-muted">
            The interactive demo renders the curated snapshot with filters and
            expandable evidence — still without calling Ollama from this site.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Link href="/demo/" className="btn-primary no-underline">
            Open the demo
          </Link>
          <Link href="/engineering/" className="btn-secondary no-underline">
            Engineering evidence
          </Link>
        </div>
      </section>
    </div>
  );
}
