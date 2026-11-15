import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MarkdownReport } from "./MarkdownReport";

afterEach(() => {
  cleanup();
});

describe("MarkdownReport", () => {
  it("renders headings and emphasis from Markdown", () => {
    render(
      <MarkdownReport markdown={"# Daily Briefing\n\n**Important** update from sources."} />,
    );
    expect(screen.getByRole("heading", { name: /Daily Briefing/i })).toBeInTheDocument();
    expect(screen.getByText("Important")).toBeInTheDocument();
  });

  it("allows only http(s) links and strips unsafe schemes", () => {
    render(
      <MarkdownReport
        markdown={
          "[Safe](https://example.com/a) and [Bad](javascript:alert(1)) and [File](file:///etc/passwd)"
        }
      />,
    );
    const safe = screen.getByRole("link", { name: "Safe" });
    expect(safe).toHaveAttribute("href", "https://example.com/a");
    expect(safe).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.queryByRole("link", { name: "Bad" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "File" })).not.toBeInTheDocument();
    expect(screen.getByText("Bad")).toBeInTheDocument();
  });

  it("does not execute or keep raw HTML script tags", () => {
    const { container } = render(
      <MarkdownReport
        markdown={"Hello <script>window.__pwned=1</script><img src=x onerror=alert(1)>"}
      />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    const report = within(container).getByTestId("markdown-report");
    expect(report.textContent).toMatch(/Hello/);
  });

  it("shows empty state when markdown is blank", () => {
    render(<MarkdownReport markdown="   " emptyLabel="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});
