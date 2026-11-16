"use client";

import { useId, useState } from "react";
import { engineeringDecisions } from "@/lib/architecture";

export function DecisionList() {
  const baseId = useId();
  const [openId, setOpenId] = useState<string | null>(engineeringDecisions[0]?.id ?? null);

  return (
    <section className="space-y-6" aria-labelledby={`${baseId}-heading`}>
      <div className="max-w-3xl">
        <h2 id={`${baseId}-heading`} className="text-3xl sm:text-4xl">
          Engineering decisions
        </h2>
        <p className="mt-3 text-muted">
          Documented product choices with expandable technical detail. No
          invented benchmarks — each item cites repository sources.
        </p>
      </div>

      <ul className="space-y-3">
        {engineeringDecisions.map((decision) => {
          const open = openId === decision.id;
          const panelId = `${baseId}-${decision.id}-panel`;
          return (
            <li key={decision.id} className="panel overflow-hidden">
              <button
                type="button"
                className="flex w-full items-start justify-between gap-4 px-5 py-4 text-left sm:px-6"
                aria-expanded={open}
                aria-controls={panelId}
                onClick={() =>
                  setOpenId((current) =>
                    current === decision.id ? null : decision.id,
                  )
                }
              >
                <span>
                  <span className="block font-display text-xl text-paper">
                    {decision.title}
                  </span>
                  <span className="mt-2 block text-sm leading-relaxed text-muted">
                    {decision.summary}
                  </span>
                </span>
                <span className="shrink-0 font-mono text-xs uppercase tracking-[0.12em] text-accent">
                  {open ? "Hide" : "Detail"}
                </span>
              </button>
              {open ? (
                <div
                  id={panelId}
                  className="space-y-3 border-t border-line/80 bg-ink-soft/35 px-5 py-4 sm:px-6"
                >
                  <p className="text-sm leading-relaxed text-muted">
                    {decision.detail}
                  </p>
                  <p className="font-mono text-xs text-muted">
                    Source: {decision.source}
                  </p>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
