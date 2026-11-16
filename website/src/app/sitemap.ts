import type { MetadataRoute } from "next";
import { absolutePublicUrl } from "@/lib/seo";

export const dynamic = "force-static";

const routes = [
  "/",
  "/demo/",
  "/how-it-works/",
  "/engineering/",
  "/under-the-hood/",
] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date("2026-11-16T00:00:00.000Z");

  return routes.map((route) => ({
    url: absolutePublicUrl(route),
    lastModified,
    changeFrequency: route === "/" ? "weekly" : "monthly",
    priority: route === "/" ? 1 : 0.7,
  }));
}
