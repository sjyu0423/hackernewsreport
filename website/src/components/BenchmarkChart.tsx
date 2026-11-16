import { m1ArticleBenchmarks, m1BenchmarkMeta } from "@/lib/benchmarks";

export function BenchmarkChart() {
  const maxLatency = Math.max(
    ...m1ArticleBenchmarks.map((row) => row.latencySeconds),
  );

  return (
    <section className="space-y-6" aria-labelledby="m1-benchmark-heading">
      <div className="max-w-3xl">
        <h2 id="m1-benchmark-heading" className="text-3xl sm:text-4xl">
          Verified M1 performance
        </h2>
        <p className="mt-3 text-muted">
          Five-article sequential benchmark on {m1BenchmarkMeta.modelId} (
          {m1BenchmarkMeta.quantization}), think=
          {String(m1BenchmarkMeta.think)}, concurrency=
          {m1BenchmarkMeta.concurrency}. Total wall time{" "}
          <strong className="font-medium text-paper">
            {m1BenchmarkMeta.totalSeconds}s
          </strong>{" "}
          ({m1BenchmarkMeta.totalSecondsExact}s measured).
        </p>
      </div>

      <div className="panel space-y-6 p-5 sm:p-7">
        <p className="eyebrow">Latency by source (seconds)</p>
        <ul className="space-y-3" aria-hidden="true">
          {m1ArticleBenchmarks.map((row) => {
            const width = `${(row.latencySeconds / maxLatency) * 100}%`;
            return (
              <li key={row.source} className="grid gap-2 sm:grid-cols-[8rem_1fr_auto] sm:items-center">
                <span className="text-sm text-muted">{row.label}</span>
                <div className="h-3 rounded-full bg-ink-soft">
                  <div
                    className="h-3 rounded-full bg-accent/80 motion-safe:transition-[width] motion-safe:duration-500"
                    style={{ width }}
                  />
                </div>
                <span className="font-mono text-xs text-paper">
                  {row.latencySeconds.toFixed(1)}s · {row.tokensPerSecond.toFixed(1)} tok/s
                </span>
              </li>
            );
          })}
        </ul>

        <div className="overflow-x-auto rounded-2xl border border-line">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">
              M1 five-article sequential benchmark latency and tokens per second
            </caption>
            <thead className="bg-ink-soft/80 text-muted">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">
                  Source
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Latency
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  tok/s
                </th>
                <th scope="col" className="px-4 py-3 font-medium">
                  Analysis label
                </th>
              </tr>
            </thead>
            <tbody>
              {m1ArticleBenchmarks.map((row) => (
                <tr key={row.source} className="border-t border-line/80">
                  <th scope="row" className="px-4 py-3 font-medium text-paper">
                    {row.label}
                  </th>
                  <td className="px-4 py-3 font-mono text-muted">
                    {row.latencySeconds.toFixed(1)}s
                  </td>
                  <td className="px-4 py-3 font-mono text-muted">
                    {row.tokensPerSecond.toFixed(1)}
                  </td>
                  <td className="px-4 py-3 text-muted">{row.evidence}</td>
                </tr>
              ))}
              <tr className="border-t border-line/80 bg-ink-soft/40">
                <th scope="row" className="px-4 py-3 font-medium text-paper">
                  Total sequential
                </th>
                <td className="px-4 py-3 font-mono text-paper">
                  {m1BenchmarkMeta.totalSeconds}s
                </td>
                <td className="px-4 py-3 text-muted">—</td>
                <td className="px-4 py-3 text-muted">5/5 schema OK</td>
              </tr>
            </tbody>
          </table>
        </div>

        <ul className="space-y-1 text-sm text-muted">
          {m1BenchmarkMeta.conditions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
