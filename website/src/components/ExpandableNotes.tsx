"use client";

import { useId, useState } from "react";

export type ExpandableNote = {
  id: string;
  title: string;
  summary: string;
  detail: string;
};

type ExpandableNotesProps = {
  heading: string;
  description?: string;
  notes: readonly ExpandableNote[];
};

export function ExpandableNotes({
  heading,
  description,
  notes,
}: ExpandableNotesProps) {
  const baseId = useId();
  const [openId, setOpenId] = useState<string | null>(notes[0]?.id ?? null);

  return (
    <section className="space-y-4" aria-labelledby={`${baseId}-heading`}>
      <div className="max-w-3xl">
        <h3 id={`${baseId}-heading`} className="text-xl text-paper sm:text-2xl">
          {heading}
        </h3>
        {description ? (
          <p className="mt-2 text-sm text-muted">{description}</p>
        ) : null}
      </div>
      <ul className="space-y-2">
        {notes.map((note) => {
          const open = openId === note.id;
          const panelId = `${baseId}-${note.id}-panel`;
          return (
            <li key={note.id} className="overflow-hidden rounded-2xl border border-line/80 bg-ink-soft/40">
              <button
                type="button"
                className="flex w-full items-start justify-between gap-4 px-4 py-3 text-left sm:px-5"
                aria-expanded={open}
                aria-controls={panelId}
                onClick={() =>
                  setOpenId((current) => (current === note.id ? null : note.id))
                }
              >
                <span>
                  <span className="block text-sm font-medium text-paper">
                    {note.title}
                  </span>
                  <span className="mt-1 block text-sm text-muted">
                    {note.summary}
                  </span>
                </span>
                <span className="shrink-0 font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
                  {open ? "Hide" : "More"}
                </span>
              </button>
              {open ? (
                <div
                  id={panelId}
                  className="border-t border-line/70 px-4 py-3 text-sm leading-relaxed text-muted sm:px-5"
                >
                  {note.detail}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
