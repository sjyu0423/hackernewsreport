"use client";

import { useRouter } from "next/navigation";

export function HistoryFilters({
  categories,
  mode,
  category,
}: {
  categories: string[];
  mode?: string;
  category?: string;
}) {
  const router = useRouter();

  function update(next: { mode?: string; category?: string }) {
    const q = new URLSearchParams();
    const m = next.mode ?? mode;
    const c = next.category ?? category;
    if (m) q.set("mode", m);
    if (c) q.set("category", c);
    const qs = q.toString();
    router.push(qs ? `/history?${qs}` : "/history");
  }

  return (
    <form className="filters" onSubmit={(e) => e.preventDefault()}>
      <label>
        Mode
        <select
          aria-label="Filter by mode"
          value={mode || ""}
          onChange={(e) => update({ mode: e.target.value || undefined, category })}
        >
          <option value="">All</option>
          <option value="daily">Daily</option>
          <option value="hourly">Hourly</option>
          <option value="ondemand">On-demand</option>
        </select>
      </label>
      <label>
        Category
        <select
          aria-label="Filter by category"
          value={category || ""}
          onChange={(e) => update({ mode, category: e.target.value || undefined })}
        >
          <option value="">All</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
    </form>
  );
}
