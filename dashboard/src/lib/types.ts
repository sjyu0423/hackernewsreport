export type ReportSummary = {
  id: number;
  mode: string | null;
  created_at: string | null;
  as_of: string | null;
  window_start: string | null;
  story_count: number;
  significant_only: boolean;
  status: string | null;
  markdown_preview: string | null;
  kind: string | null;
};

export type ReportDetail = ReportSummary & {
  markdown: string;
  hours: number | null;
};

export type StoryArticle = {
  id: string;
  title: string;
  canonical_url: string | null;
  sources: string | null;
  discovered_at: string | null;
  published_at: string | null;
  link_reason: string | null;
  summary: string | null;
  why_it_matters: string | null;
  category: string | null;
  relevance_score: number | null;
  significance_score: number | null;
};

export type StoryCard = {
  id: string;
  title: string;
  category: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  significant_update_at: string | null;
  article_count: number;
  primary: StoryArticle | null;
  articles: StoryArticle[];
};

export type TodayResponse = {
  source: string;
  fallback_reason: string | null;
  report: ReportDetail | null;
  stories: StoryCard[];
};

export type StatusResponse = {
  db: Record<string, unknown>;
  watermarks: Record<string, unknown>;
  backlog: Record<string, number>;
  recent_runs: Array<Record<string, unknown>>;
  last_hourly_report: ReportSummary | null;
  last_daily_report: ReportSummary | null;
  ollama: Record<string, unknown> | null;
  ollama_live: boolean;
  note: string;
};
