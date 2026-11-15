import type {
  ReportDetail,
  ReportSummary,
  StatusResponse,
  StoryCard,
  TodayResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_QWENNEWS_API_BASE?.replace(/\/$/, "") ||
  "http://127.0.0.1:8765";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function getApiBase(): string {
  return API_BASE;
}

export function fetchToday(): Promise<TodayResponse> {
  return getJson("/api/today");
}

export function fetchHourly(limit = 24): Promise<{ items: ReportSummary[] }> {
  return getJson(`/api/hourly?limit=${limit}`);
}

export function fetchStories(limit = 40, category?: string): Promise<StoryCard[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (category) q.set("category", category);
  return getJson(`/api/stories?${q.toString()}`);
}

export function fetchHistory(params: {
  mode?: string;
  category?: string;
  limit?: number;
}): Promise<{ items: ReportSummary[]; categories: string[] }> {
  const q = new URLSearchParams();
  if (params.mode) q.set("mode", params.mode);
  if (params.category) q.set("category", params.category);
  q.set("limit", String(params.limit ?? 40));
  return getJson(`/api/reports?${q.toString()}`);
}

export function fetchReport(id: number): Promise<ReportDetail> {
  return getJson(`/api/reports/${id}`);
}

export function fetchStatus(): Promise<StatusResponse> {
  return getJson("/api/status");
}

export function fetchHealth(): Promise<{ ok: boolean }> {
  return getJson("/api/health");
}
