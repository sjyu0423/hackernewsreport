type CodeSchematicProps = {
  title: string;
  input: string;
  output: string;
  notes: readonly string[];
};

export function CodeSchematic({
  title,
  input,
  output,
  notes,
}: CodeSchematicProps) {
  return (
    <figure className="panel space-y-4 p-5 sm:p-6">
      <figcaption className="eyebrow">{title}</figcaption>
      <div className="grid gap-4 lg:grid-cols-2">
        <pre
          className="overflow-x-auto rounded-xl border border-line/80 bg-ink/60 p-4 font-mono text-xs leading-relaxed text-paper/90"
          tabIndex={0}
        >
          <span className="mb-2 block font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
            Schematic input
          </span>
          {input}
        </pre>
        <pre
          className="overflow-x-auto rounded-xl border border-line/80 bg-ink/60 p-4 font-mono text-xs leading-relaxed text-paper/90"
          tabIndex={0}
        >
          <span className="mb-2 block font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
            Validated output shape
          </span>
          {output}
        </pre>
      </div>
      <ul className="space-y-1 text-sm text-muted">
        {notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </figure>
  );
}
