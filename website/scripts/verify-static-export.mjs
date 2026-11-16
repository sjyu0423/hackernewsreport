#!/usr/bin/env node
/**
 * Post-build checks for the public static export.
 * Ensures expected routes exist and sensitive artifacts are not bundled.
 */
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = process.cwd();
const outDir = join(root, "out");

const requiredRoutes = [
  "index.html",
  "demo/index.html",
  "how-it-works/index.html",
  "engineering/index.html",
  "under-the-hood/index.html",
  "404.html",
];

const forbiddenNamePatterns = [
  /\.db$/i,
  /\.sqlite3?$/i,
  /^\.env/i,
  /live_m0/i,
  /launchagent/i,
];

const forbiddenContentSnippets = [
  "127.0.0.1:8765",
  "QWENNEWS_DB_PATH",
  "localhost:11434",
  "/api/chat",
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
    fail(`missing exported route: ${route}`);
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

const htmlFiles = files.filter((f) => f.endsWith(".html") || f.endsWith(".js"));
for (const file of htmlFiles) {
  const text = readFileSync(file, "utf8");
  for (const snippet of forbiddenContentSnippets) {
    if (text.includes(snippet)) {
      fail(`export contains sensitive runtime reference "${snippet}" in ${relative(outDir, file)}`);
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

const demoHtml = readFileSync(join(outDir, "demo/index.html"), "utf8");
if (!demoHtml.includes("Fixed snapshot") && !demoHtml.includes("fixed snapshot")) {
  // Client component text may live in JS chunks; check bundled JS too.
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

console.log(`verify-static-export: ok (${files.length} files, ${requiredRoutes.length} routes)`);
