import type { NextConfig } from "next";

/**
 * GitHub Pages project sites are served under /<repository>.
 * Set NEXT_PUBLIC_BASE_PATH at build time (example: /hackernewsreport).
 * Leave unset for local `next dev` and for custom domains at the site root.
 *
 * Observed GitHub remote for this checkout: sjyu0423/hackernewsreport
 * → likely project-pages path /hackernewsreport once Pages is enabled.
 * Do not treat that as an authorized deployment target until configured.
 */
const rawBasePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const basePath = rawBasePath === "/" ? "" : rawBasePath.replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath: basePath || undefined,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
