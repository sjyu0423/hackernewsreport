"use client";

import { useId, useState } from "react";
import {
  type ArchitectureStageId,
  architectureStages,
  getStage,
  nextStageId,
} from "@/lib/architecture";

export function ArchitectureFlow() {
  const [activeId, setActiveId] = useState<ArchitectureStageId>("collect");
  const baseId = useId();
  const active = getStage(activeId);

  return (
    <section className="space-y-5" aria-labelledby={`${baseId}-heading`}>
      <div className="max-w-3xl">
        <h2 id={`${baseId}-heading`} className="text-3xl sm:text-4xl">
          Interactive pipeline
        </h2>
        <p className="mt-3 text-muted">
          Select a stage to see what enters, what happens, and what leaves.
          Qwen only participates in local analysis — Python owns orchestration.
        </p>
      </div>

      <div
        role="tablist"
        aria-label="Architecture stages"
        aria-orientation="horizontal"
        className="flex flex-col gap-2 lg:flex-row lg:items-stretch"
        onKeyDown={(event) => {
          const focusStage = (id: ArchitectureStageId) => {
            setActiveId(id);
            requestAnimationFrame(() => {
              document.getElementById(`${baseId}-tab-${id}`)?.focus();
            });
          };

          if (event.key === "ArrowRight" || event.key === "ArrowDown") {
            event.preventDefault();
            focusStage(nextStageId(activeId, 1));
          }
          if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
            event.preventDefault();
            focusStage(nextStageId(activeId, -1));
          }
          if (event.key === "Home") {
            event.preventDefault();
            focusStage("collect");
          }
          if (event.key === "End") {
            event.preventDefault();
            focusStage("publish");
          }
        }}
      >
        {architectureStages.map((stage, index) => {
          const selected = stage.id === activeId;
          const tabId = `${baseId}-tab-${stage.id}`;
          const panelId = `${baseId}-panel`;
          return (
            <div key={stage.id} className="flex flex-1 items-stretch gap-2">
              <button
                type="button"
                role="tab"
                id={tabId}
                aria-selected={selected}
                aria-controls={panelId}
                tabIndex={selected ? 0 : -1}
                className={`w-full rounded-2xl border px-4 py-4 text-left transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                  selected
                    ? "border-accent/50 bg-accent-soft shadow-panel"
                    : "border-line/80 bg-ink-elevated/50 hover:border-accent/30 hover:bg-ink-soft/70"
                }`}
                onClick={() => setActiveId(stage.id)}
              >
                <p className="font-mono text-[0.7rem] uppercase tracking-[0.16em] text-accent">
                  {stage.step}
                </p>
                <p className="mt-1 font-display text-lg text-paper">
                  {stage.shortLabel}
                </p>
                <p className="mt-1 text-xs text-muted lg:line-clamp-2">
                  {stage.ownerLabel}
                </p>
              </button>
              {index < architectureStages.length - 1 ? (
                <div
                  className="hidden w-3 shrink-0 items-center justify-center text-muted lg:flex"
                  aria-hidden="true"
                >
                  →
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`${baseId}-panel`}
        aria-labelledby={`${baseId}-tab-${active.id}`}
        className="panel fade-rise space-y-6 p-5 sm:p-7"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="eyebrow">
              Stage {active.step} · {active.ownerLabel}
            </p>
            <h3 className="mt-2 text-2xl sm:text-3xl">{active.title}</h3>
            <p className="mt-3 max-w-3xl text-muted">{active.summary}</p>
          </div>
          <span className="status-chip">
            <span className="status-dot" aria-hidden="true" />
            {active.owner === "model"
              ? "Model"
              : active.owner === "mixed"
                ? "Mixed"
                : "Python"}
          </span>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <StageColumn title="Enters" items={active.inputs} />
          <StageColumn title="Does" items={active.process} />
          <StageColumn title="Produces" items={active.outputs} />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-line/80 bg-ink-soft/40 p-4">
            <h4 className="text-sm font-medium text-paper">Why it exists</h4>
            <p className="mt-2 text-sm leading-relaxed text-muted">{active.why}</p>
          </div>
          <div className="rounded-2xl border border-line/80 bg-ink-soft/40 p-4">
            <h4 className="text-sm font-medium text-paper">Grounded example</h4>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              {active.example}
            </p>
          </div>
        </div>

        <p className="text-xs text-muted">
          Keyboard: Left/Right or Up/Down to move between stages. Home/End jump
          to Collect/Publish.
        </p>
      </div>
    </section>
  );
}

function StageColumn({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-2xl border border-line/80 bg-ink-elevated/40 p-4">
      <h4 className="font-mono text-xs uppercase tracking-[0.14em] text-violet">
        {title}
      </h4>
      <ul className="mt-3 space-y-2 text-sm leading-relaxed text-muted">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
