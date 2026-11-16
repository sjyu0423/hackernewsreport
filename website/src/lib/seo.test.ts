import { describe, expect, it } from "vitest";
import {
  absolutePublicUrl,
  openGraphImage,
  productionBasePath,
  productionSiteUrl,
  resolveSiteUrl,
  routeMeta,
} from "./seo";
import { siteConfig } from "./site";

describe("production publishing targets", () => {
  it("points at the intended GitHub Pages project URL", () => {
    expect(productionSiteUrl).toBe(
      "https://sjyu0423.github.io/hackernewsreport",
    );
    expect(productionBasePath).toBe("/hackernewsreport");
    expect(siteConfig.githubUrl).toBe(
      "https://github.com/sjyu0423/hackernewsreport",
    );
  });

  it("builds absolute URLs without doubling the project path", () => {
    expect(resolveSiteUrl()).toMatch(/^https:\/\//);
    expect(absolutePublicUrl("/demo/")).toBe(
      `${productionSiteUrl}/demo/`,
    );
    expect(absolutePublicUrl("/demo/")).not.toContain(
      "/hackernewsreport/hackernewsreport",
    );
    expect(openGraphImage.path).toBe("/og-share.jpg");
    expect(openGraphImage.alt.toLowerCase()).toContain("qwennews");
  });
});

describe("routeMeta", () => {
  it("keeps pretrained-model wording in key descriptions", () => {
    expect(routeMeta.home.description.toLowerCase()).toContain("pretrained");
    expect(routeMeta.howItWorks.description.toLowerCase()).toContain(
      "pretrained",
    );
    expect(siteConfig.description.toLowerCase()).toContain("pretrained");
    expect(siteConfig.description.toLowerCase()).toContain("not trained");
  });
});
