import type { Metadata } from "next";
import Link from "next/link";
import { CodeSchematic } from "@/components/CodeSchematic";
import { DataFlowDiagram } from "@/components/DataFlowDiagram";
import { ExpandableNotes } from "@/components/ExpandableNotes";
import { PageHero } from "@/components/PageHero";
import {
  analysisFieldOwnership,
  correctedClaims,
  dedupeNotes,
  doNotClaim,
  localInferenceNotes,
  rankingFormula,
  reliabilityGuarantees,
  schematicIoExample,
  schemaExpandables,
  underHoodLinks,
} from "@/lib/under-the-hood";

export const metadata: Metadata = {
  title: "Under the Hood",
  description:
    "Technical deep dive for QwenNews: local inference contracts, SQLite memory model, ranking and deduplication, and reliability guarantees — grounded in application source.",
};

export default function UnderTheHoodPage() {
  return (
    <div className="shell space-y-16 pb-20">
      <PageHero
        eyebrow="Under the Hood"
        title="Technical appendix for reviewers"
        description="Optional depth for engineers who already understand the product story. Descriptions track application source and milestone docs — not a duplicate of How It Works or Engineering evidence."
      >
        <div className="flex flex-wrap gap-3">
          <Link href="/how-it-works/" className="btn-secondary no-underline">
            Architecture walkthrough
          </Link>
          <Link href="/engineering/" className="btn-secondary no-underline">
            Engineering evidence
          </Link>
          <a
            href={underHoodLinks.architecture}
            className="btn-secondary no-underline"
            rel="noopener noreferrer"
            target="_blank"
          >
            docs/architecture.md
          </a>
        </div>
      </PageHero>

      <section className="space-y-6" aria-labelledby="inference-heading">
        <div className="max-w-3xl">
          <h2 id="inference-heading" className="text-3xl sm:text-4xl">
            Local inference contract
          </h2>
          <p className="mt-3 text-muted">
            Ollama serves pretrained Qwen3 4B on loopback. Structured JSON is
            schema-constrained and Pydantic-validated before anything is cached.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {localInferenceNotes.map((note) => (
            <article key={note.title} className="panel space-y-2 p-5">
              <h3 className="text-lg text-paper">{note.title}</h3>
              <p className="text-sm leading-relaxed text-muted">{note.body}</p>
            </article>
          ))}
        </div>

        <div className="overflow-x-auto rounded-2xl border border-line">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">
              Field ownership between model output and application state
            </caption>
            <thead className="bg-ink-soft/80 text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">
                  Fields
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Owner
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Detail
                </th>
              </tr>
            </thead>
            <tbody>
              {analysisFieldOwnership.map((row) => (
                <tr key={row.field} className="border-t border-line/80">
                  <th
                    scope="row"
                    className="px-4 py-3 font-mono text-xs font-medium text-paper"
                  >
                    {row.field}
                  </th>
                  <td className="px-4 py-3 text-muted">{row.owner}</td>
                  <td className="px-4 py-3 text-muted">{row.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <CodeSchematic
          title={schematicIoExample.label}
          input={schematicIoExample.input}
          output={schematicIoExample.output}
          notes={schematicIoExample.notes}
        />

        <ExpandableNotes
          heading="Schema notes"
          description="Expand for cache and field bounds without dumping private prompts."
          notes={schemaExpandables}
        />
      </section>

      <section className="space-y-6" aria-labelledby="memory-heading">
        <div className="max-w-3xl">
          <h2 id="memory-heading" className="text-3xl sm:text-4xl">
            Data and memory
          </h2>
          <p className="mt-3 text-muted">
            SQLite is the durable news memory. Hourly and daily report state is
            independent: each mode has its own watermark and per-story reported
            markers so one cadence cannot silently consume the other.
          </p>
        </div>
        <DataFlowDiagram />
        <p className="max-w-3xl text-sm text-muted">
          Update detection: meaningful content change (Jaccard / new tokens)
          versus metadata-only HN churn. Report deltas compare story first-seen /
          significant-update times against the mode watermark and{" "}
          <code className="font-mono text-paper/85">story_report_state</code>.
        </p>
      </section>

      <section className="space-y-6" aria-labelledby="ranking-heading">
        <div className="max-w-3xl">
          <h2 id="ranking-heading" className="text-3xl sm:text-4xl">
            Ranking and deduplication
          </h2>
          <p className="mt-3 text-muted">
            Model scores feed a deterministic Python blend. Near-duplicate linking
            is intentionally conservative.
          </p>
        </div>

        <div className="panel space-y-4 p-5 sm:p-6">
          <p className="eyebrow">M2 rank score</p>
          <pre
            className="overflow-x-auto rounded-xl border border-line/80 bg-ink/60 p-4 font-mono text-xs leading-relaxed text-paper/90 sm:text-sm"
            tabIndex={0}
          >
            {rankingFormula.expression}
          </pre>
          <p className="font-mono text-xs text-muted">{rankingFormula.source}</p>
          <ul className="space-y-2 text-sm text-muted">
            {rankingFormula.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {dedupeNotes.map((note) => (
            <article key={note.title} className="panel space-y-2 p-5">
              <h3 className="text-lg text-paper">{note.title}</h3>
              <p className="text-sm leading-relaxed text-muted">{note.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="space-y-6" aria-labelledby="reliability-heading">
        <div className="max-w-3xl">
          <h2 id="reliability-heading" className="text-3xl sm:text-4xl">
            Reliability boundaries
          </h2>
          <p className="mt-3 text-muted">
            Each row separates application behavior, what tests cover, and what
            this page does not claim as operational proof.
          </p>
        </div>

        <div className="space-y-4">
          {reliabilityGuarantees.map((item) => (
            <article key={item.title} className="panel space-y-4 p-5 sm:p-6">
              <h3 className="text-xl text-paper">{item.title}</h3>
              <dl className="grid gap-4 md:grid-cols-3">
                <div>
                  <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
                    Application
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-muted">
                    {item.application}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
                    Tests
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-muted">
                    {item.verified}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
                    Not claimed
                  </dt>
                  <dd className="mt-2 text-sm leading-relaxed text-muted">
                    {item.notClaimed}
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>

        <p className="max-w-3xl text-sm text-muted">
          LaunchAgent honesty also appears on{" "}
          <Link href="/engineering/" className="no-underline">
            Engineering
          </Link>
          . See{" "}
          <a
            href={underHoodLinks.m4_2}
            rel="noopener noreferrer"
            target="_blank"
          >
            M4.2 notes
          </a>
          .
        </p>
      </section>

      <section className="space-y-6" aria-labelledby="corrections-heading">
        <div className="max-w-3xl">
          <h2 id="corrections-heading" className="text-3xl sm:text-4xl">
            Corrected assumptions
          </h2>
          <p className="mt-3 text-muted">
            Where earlier docs or copy could be misread, the public site follows
            current code.
          </p>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-line">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">
              Corrected claims versus application source
            </caption>
            <thead className="bg-ink-soft/80 text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">
                  Easy misreading
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Actual
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Source
                </th>
              </tr>
            </thead>
            <tbody>
              {correctedClaims.map((row) => (
                <tr key={row.claim} className="border-t border-line/80">
                  <th scope="row" className="px-4 py-3 font-medium text-paper">
                    {row.claim}
                  </th>
                  <td className="px-4 py-3 text-muted">{row.actual}</td>
                  <td className="px-4 py-3 font-mono text-xs text-muted">
                    {row.source}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel space-y-3 p-5">
          <p className="eyebrow">Do not claim</p>
          <ul className="space-y-2 text-sm text-muted">
            {doNotClaim.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
