import { describe, expect, it } from "vitest";
import {
  analysisFieldOwnership,
  correctedClaims,
  dataFlowNodes,
  doNotClaim,
  rankingFormula,
  reliabilityGuarantees,
  schematicIoExample,
  schemaExpandables,
} from "./under-the-hood";

describe("rankingFormula", () => {
  it("matches compute_rank_score_m2 weights from ranking.py", () => {
    expect(rankingFormula.expression).toContain("0.35·significance");
    expect(rankingFormula.expression).toContain("0.25·relevance");
    expect(rankingFormula.expression).toContain("0.25·category_priority");
    expect(rankingFormula.expression).toContain("0.10·ai_signal");
    expect(rankingFormula.expression).toContain("0.05·hn_attention_capped");
    expect(rankingFormula.source).toContain("ranking.py");
  });
});

describe("schematicIoExample", () => {
  it("stays public-safe and schema-shaped", () => {
    expect(schematicIoExample.output).toContain("evidence_sufficiency");
    expect(schematicIoExample.output).toContain("relevance_score");
    expect(schematicIoExample.output).not.toMatch(/QWENNEWS_|\/Users\/|live_m0\.db/);
    expect(schematicIoExample.input).not.toMatch(/127\.0\.0\.1:11434|localhost:8765/);
    for (const note of schematicIoExample.notes) {
      expect(note.toLowerCase()).not.toContain("/users/");
    }
  });
});

describe("dataFlowNodes", () => {
  it("covers articles through mode-specific watermarks", () => {
    const ids = dataFlowNodes.map((node) => node.id);
    expect(ids).toEqual([
      "articles",
      "analyses",
      "stories",
      "processing",
      "reports",
      "watermarks",
    ]);
  });
});

describe("ownership and reliability copy", () => {
  it("keeps article_id application-owned", () => {
    const articleId = analysisFieldOwnership.find((row) =>
      row.field.includes("article_id"),
    );
    expect(articleId?.owner).toMatch(/Application/i);
  });

  it("distinguishes tests from operational LaunchAgent proof", () => {
    const launchd = reliabilityGuarantees.find((item) =>
      item.title.toLowerCase().includes("launchd"),
    );
    expect(launchd?.notClaimed.toLowerCase()).toMatch(/timer/);
    expect(doNotClaim.some((item) => item.toLowerCase().includes("launchagent"))).toBe(
      true,
    );
  });

  it("records schema v6 correction", () => {
    expect(
      correctedClaims.some((row) => row.actual.includes('schema_version = "6"')),
    ).toBe(true);
    expect(schemaExpandables.length).toBeGreaterThan(0);
  });
});
