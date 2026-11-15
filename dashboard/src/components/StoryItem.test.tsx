import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StoryItem } from "./StoryItem";
import type { StoryCard } from "@/lib/types";

const story: StoryCard = {
  id: "story_1",
  title: "Gemini 4 Hydrogen ships",
  category: "models",
  first_seen_at: "2026-11-15T18:00:00Z",
  last_seen_at: "2026-11-15T20:00:00Z",
  significant_update_at: null,
  article_count: 1,
  primary: {
    id: "a1",
    title: "Gemini 4 Hydrogen ships",
    canonical_url: "https://example.com/gemini",
    sources: "openai",
    discovered_at: "2026-11-15T18:00:00Z",
    published_at: null,
    link_reason: "new_story",
    summary: "Grounded summary for the fixture story card.",
    why_it_matters: "Useful for dashboard readers.",
    category: "models",
    relevance_score: 5,
    significance_score: 5,
  },
  articles: [],
};

describe("StoryItem", () => {
  it("renders title, summary, attribution, and safe source link", () => {
    render(<StoryItem story={story} />);
    expect(screen.getByRole("heading", { name: /Gemini 4 Hydrogen/i })).toBeInTheDocument();
    expect(screen.getByText(/Grounded summary/i)).toBeInTheDocument();
    expect(screen.getByText(/Source attribution/i)).toBeInTheDocument();
    expect(screen.getByText(/Article published/i)).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Open original source/i });
    expect(link).toHaveAttribute("href", "https://example.com/gemini");
  });

  it("handles empty stories without crashing", () => {
    const empty: StoryCard = {
      ...story,
      primary: null,
      article_count: 0,
      title: "Untitled shell",
    };
    render(<StoryItem story={empty} />);
    expect(screen.getByText(/No safe source URL/i)).toBeInTheDocument();
  });
});
