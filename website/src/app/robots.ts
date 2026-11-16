import type { MetadataRoute } from "next";
import { absolutePublicUrl, resolveSiteUrl } from "@/lib/seo";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: absolutePublicUrl("/sitemap.xml"),
    host: resolveSiteUrl(),
  };
}
