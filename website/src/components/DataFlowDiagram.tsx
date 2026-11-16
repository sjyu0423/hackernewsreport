import {
  dataFlowEdges,
  dataFlowNodes,
  schemaVersionNote,
} from "@/lib/under-the-hood";

export function DataFlowDiagram() {
  return (
    <div className="space-y-5">
      <p className="max-w-3xl text-sm text-muted">{schemaVersionNote}</p>

      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {dataFlowNodes.map((node, index) => (
          <li
            key={node.id}
            className="rounded-2xl border border-line/80 bg-ink-soft/40 p-4"
          >
            <p className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-accent">
              {String(index + 1).padStart(2, "0")} · {node.label}
            </p>
            <p className="mt-2 text-sm leading-relaxed text-muted">{node.role}</p>
          </li>
        ))}
      </ol>

      <div
        className="panel space-y-3 p-5"
        role="img"
        aria-label="Simplified data flow from articles through analyses, stories, processing, reports, and mode-specific watermarks"
      >
        <p className="eyebrow">Simplified flow</p>
        <p className="font-mono text-xs leading-relaxed text-paper/90 sm:text-sm">
          articles → article_analyses → stories/story_articles → processing
          states → reports → report_watermarks / story_report_state
        </p>
        <ul className="space-y-2 text-sm text-muted">
          {dataFlowEdges.map((edge) => (
            <li key={edge}>{edge}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
