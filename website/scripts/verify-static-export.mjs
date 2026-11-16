#!/usr/bin/env node
/**
 * Post-build checks for the public static export.
 * Ensures expected routes exist and sensitive artifacts are not bundled.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = process.cwd();
const outDir = join(root, "out");
const basePath = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");
const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "").replace(/\/$/, "");

const requiredRoutes = [
  "index.html",
  "demo/index.html",
  "how-it-works/index.html",
  "engineering/index.html",
  "under-the-hood/index.html",
  "404.html",
  "robots.txt",
  "sitemap.xml",
  "og-share.jpg",
  "icon.svg",
];

const forbiddenNamePatterns = [
  /\.db$/i,
  /\.sqlite3?$/i,
  /^\.env/i,
  /live_m0/i,
  /launchagent/i,
  /\.pem$/i,
];

// Catch private runtime wiring, not educational prose about local components.
const forbiddenContentSnippets = [
  "127.0.0.1:8765",
  "127.0.0.1:11434",
  "QWENNEWS_DB_PATH",
  "localhost:11434",
  "localhost:8765",
  "/Users/",
  "QWENNEWS_DASHBOARD_DB",
];

function walk(dir, files = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      walk(full, files);
    } else {
      files.push(full);
    }
  }
  return files;
}

function fail(message) {
  console.error(`verify-static-export: ${message}`);
  process.exit(1);
}

if (!existsSync(outDir)) {
  fail("missing out/ — run `npm run build` first");
}

for (const route of requiredRoutes) {
  const path = join(outDir, route);
  if (!existsSync(path)) {
    fail(`missing exported route/asset: ${route}`);
  }
}

const files = walk(outDir);
for (const file of files) {
  const rel = relative(outDir, file);
  const base = rel.split(/[\\/]/).pop() ?? rel;
  if (forbiddenNamePatterns.some((re) => re.test(base) || re.test(rel))) {
    fail(`forbidden artifact in export: ${rel}`);
  }
}

const textFiles = files.filter(
  (f) =>
    f.endsWith(".html") ||
    f.endsWith(".js") ||
    f.endsWith(".css") ||
    f.endsWith(".txt") ||
    f.endsWith(".xml") ||
    f.endsWith(".json") ||
    f.endsWith(".map"),
);

for (const file of textFiles) {
  const text = readFileSync(file, "utf8");
  for (const snippet of forbiddenContentSnippets) {
    if (text.includes(snippet)) {
      fail(
        `export contains sensitive runtime reference "${snippet}" in ${relative(outDir, file)}`,
      );
    }
  }
}

const sampleHtml = readFileSync(join(outDir, "index.html"), "utf8");
if (!sampleHtml.includes("QwenNews")) {
  fail("index.html missing expected brand text");
}
if (!sampleHtml.includes("Your own AI news analyst")) {
  fail("index.html missing homepage hero copy");
}
if (!sampleHtml.toLowerCase().includes("pretrained")) {
  fail("index.html missing pretrained-model disclosure");
}

const demoHtml = readFileSync(join(outDir, "demo/index.html"), "utf8");
if (!demoHtml.includes("Fixed snapshot") && !demoHtml.includes("fixed snapshot")) {
  const jsMentionsSnapshot = files.some((file) => {
    if (!file.endsWith(".js")) return false;
    const text = readFileSync(file, "utf8");
    return text.includes("Fixed snapshot") || text.includes("w1-2026-11-16");
  });
  if (!jsMentionsSnapshot) {
    fail("demo export missing snapshot disclosure markers");
  }
}

const fixturePath = join(root, "content/fixtures/demo-briefing.snapshot.json");
if (!existsSync(fixturePath)) {
  fail("missing curated demo snapshot fixture");
}

const howHtml = readFileSync(join(outDir, "how-it-works/index.html"), "utf8");
if (!howHtml.includes("How QwenNews turns public news")) {
  fail("how-it-works export missing architecture hero copy");
}

const robots = readFileSync(join(outDir, "robots.txt"), "utf8");
if (!robots.includes("Allow:") && !robots.includes("Allow: /")) {
  fail("robots.txt missing Allow rule");
}
if (!robots.includes("Sitemap:")) {
  fail("robots.txt missing Sitemap");
}

const sitemap = readFileSync(join(outDir, "sitemap.xml"), "utf8");
if (sitemap.includes("/hackernewsreport/hackernewsreport")) {
  fail("sitemap.xml double-prefixed basePath onto SITE_URL");
}
if (robots.includes("/hackernewsreport/hackernewsreport")) {
  fail("robots.txt double-prefixed basePath onto SITE_URL");
}
for (const route of [
  "/demo/",
  "/how-it-works/",
  "/engineering/",
  "/under-the-hood/",
]) {
  if (!sitemap.includes(route)) {
    fail(`sitemap.xml missing route coverage for ${route}`);
  }
}
if (!sitemap.includes("sjyu0423.github.io/hackernewsreport")) {
  fail("sitemap.xml missing intended GitHub Pages host/path");
}

if (basePath) {
  const assetNeedle = `${basePath}/_next/`;
  if (!sampleHtml.includes(assetNeedle) && !sampleHtml.includes(`${basePath}/`)) {
    fail(`index.html missing basePath asset prefix ${basePath}`);
  }
}

if (siteUrl && !sitemap.includes(siteUrl) && !robots.includes(siteUrl)) {
  // metadataBase / sitemap should reference configured site URL when provided
  if (!sitemap.includes("sjyu0423.github.io")) {
    fail("sitemap.xml missing expected site host when SITE_URL configured");
  }
}

const mapFiles = files.filter((f) => f.endsWith(".map"));
for (const mapFile of mapFiles) {
  const text = readFileSync(mapFile, "utf8");
  if (text.includes("/Users/") || text.includes("QWENNEWS_DB_PATH")) {
    fail(`source map exposes private path: ${relative(outDir, mapFile)}`);
  }
}

console.log(
  `verify-static-export: ok (${files.length} files, ${requiredRoutes.length} required, basePath=${basePath || "(none)"})`,
);
