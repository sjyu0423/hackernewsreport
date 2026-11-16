import { describe, expect, it } from "vitest";
import {
  architectureStageIds,
  architectureStages,
  buildArticleJourney,
  engineeringDecisions,
  getStage,
  nextStageId,
  systemBoundaries,
} from "./architecture";
import { demoSnapshot } from "./demo";

describe("architectureStages", () => {
  it("defines five stages in pipeline order", () => {
    expect(architectureStages.map((stage) => stage.id)).toEqual([
      "collect",
      "store",
      "analyze",
      "rank",
      "publish",
    ]);
    expect(architectureStageIds).toHaveLength(5);
  });

  it("keeps model inference scoped to the analyze stage", () => {
    const analyze = getStage("analyze");
    expect(analyze.owner).toBe("mixed");
    expect(analyze.process.some((item) => item.includes("Ollama"))).toBe(true);

    for (const stage of architectureStages.filter((item) => item.id !== "analyze")) {
      expect(stage.owner).not.toBe("model");
    }
  });

  it("includes enter/do/produce/why content for each stage", () => {
    for (const stage of architectureStages) {
      expect(stage.inputs.length).toBeGreaterThan(0);
      expect(stage.process.length).toBeGreaterThan(0);
      expect(stage.outputs.length).toBeGreaterThan(0);
      expect(stage.why.length).toBeGreaterThan(10);
    }
  });
});

describe("nextStageId", () => {
  it("moves forward and wraps", () => {
    expect(nextStageId("collect", 1)).toBe("store");
    expect(nextStageId("publish", 1)).toBe("collect");
  });

  it("moves backward and wraps", () => {
    expect(nextStageId("store", -1)).toBe("collect");
    expect(nextStageId("collect", -1)).toBe("publish");
  });
});

describe("buildArticleJourney", () => {
  it("uses an actual curated snapshot story", () => {
    const journey = buildArticleJourney();
    expect(demoSnapshot.items.some((item) => item.id === journey.story.id)).toBe(
      true,
    );
    expect(journey.steps).toHaveLength(5);
    expect(journey.steps.filter((step) => step.kind === "actual").length).toBeGreaterThanOrEqual(
      2,
    );
    expect(journey.steps.some((step) => step.kind === "schematic")).toBe(true);
    expect(journey.story.summary.length).toBeGreaterThan(20);
    expect(journey.story.source_url.startsWith("http")).toBe(true);
  });
});

describe("decisions and boundaries", () => {
  it("documents required engineering decisions", () => {
    const ids = engineeringDecisions.map((item) => item.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        "local-inference",
        "sqlite",
        "near-dupes",
        "deterministic-reports",
        "bounded-inference",
        "watermarks",
        "readonly-api",
      ]),
    );
  });

  it("separates local app, public site, and private dashboard", () => {
    expect(systemBoundaries.map((item) => item.id)).toEqual([
      "local-app",
      "public-site",
      "private-dashboard",
    ]);
    const publicSite = systemBoundaries.find((item) => item.id === "public-site");
    expect(publicSite?.doesNot.join(" ")).toMatch(/Ollama|SQLite/i);
  });
});
