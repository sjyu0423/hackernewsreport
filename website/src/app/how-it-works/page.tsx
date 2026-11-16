import type { Metadata } from "next";
import { ComingSoonPanel } from "@/components/ComingSoonPanel";
import { PageHero } from "@/components/PageHero";
import { stackRoles } from "@/lib/site";

export const metadata: Metadata = {
  title: "How It Works",
  description:
    "Architecture overview for QwenNews: ingestion, SQLite memory, local Qwen3 4B analysis, reporting, and scheduling.",
};

const pipeline = [
  {
    step: "01",
    title: "Collect",
    body: "Pull Hacker News and verified AI/tech RSS sources, normalize articles, and respect robots and SSRF safeguards.",
  },
  {
    step: "02",
    title: "Remember",
    body: "Persist articles and story links in SQLite so later runs can detect updates instead of treating every sighting as new.",
  },
  {
    step: "03",
    title: "Analyze",
    body: "Ask a local Qwen3 4B model (via Ollama) for structured summaries and scores; validate and cache the result.",
  },
  {
    step: "04",
    title: "Report",
    body: "Rank and render hourly deltas or daily digests. Optional LaunchAgents automate the cycle on macOS.",
  },
] as const;

export default function HowItWorksPage() {
  return (
    <div className="shell space-y-12 pb-20">
      <PageHero
        eyebrow="How It Works"
        title="From public feeds to a local briefing"
        description="QwenNews is an orchestration system around a pretrained local model — not a custom-trained news LLM."
      />

      <ol className="grid gap-4 md:grid-cols-2">
        {pipeline.map((item) => (
          <li
            key={item.step}
            className="rounded-2xl border border-line/80 bg-ink-elevated/55 p-5"
          >
            <p className="font-mono text-xs uppercase tracking-[0.16em] text-accent">
              {item.step}
            </p>
            <h2 className="mt-2 text-2xl">{item.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">{item.body}</p>
          </li>
        ))}
      </ol>

      <section className="space-y-4">
        <h2 className="text-3xl">System roles</h2>
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

      <ComingSoonPanel
        milestone="W2"
        title="Deeper architecture narrative"
        summary="W0 records the verified pipeline shape. Later work will expand diagrams, failure policy, and the boundary between this public site and the private dashboard."
        planned={[
          "End-to-end architecture diagram",
          "Failure and watermark policy explanation",
          "Public site vs private dashboard boundary",
          "Source and safety constraints (robots, SSRF)",
        ]}
      />
    </div>
  );
}
