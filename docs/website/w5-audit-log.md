# W5 cross-page factual audit log

**Date:** 2026-11-16  
**Branch:** `website-w5-release`  
**Intended public URL (not claimed live):** https://sjyu0423.github.io/hackernewsreport/

## Checks performed

| Check | Result |
| --- | --- |
| Model described as pretrained Qwen3 4B via Ollama (not trained here) | Pass (homepage hero clarified in W5) |
| Five sources: HN, OpenAI, DeepMind, Hugging Face, TechCrunch AI | Pass (`evidence.ts`, architecture collect stage) |
| M1 benchmarks match milestone figures + conditions/date | Pass (`benchmarks.ts`) |
| Schematic / simulation labels present | Pass (architecture, backlog explorer, under-the-hood I/O) |
| Demo = curated static snapshot, not live inference | Pass |
| LaunchAgent timer fire not claimed verified | Pass (engineering + under-the-hood honesty) |
| Test counts dated / historical | Pass |
| Watermarks / schema / ownership consistent across pages | Pass after W4 corrections; W5 softens one cache wording |
| External http(s) links only | Pass |

## Corrections applied in W5

1. **Homepage hero** — state explicitly that Qwen3 4B is **pretrained** and served through Ollama (not trained/fine-tuned here).
2. **Architecture decision “Bounded inference and caching”** — remove overclaim that M1 “confirmed” quiet-path wall-time savings; keep cache-key behavior and point readers to Engineering for measured cycles (different workloads).
3. **How It Works metadata** — say **pretrained** Qwen3 4B for SEO consistency.
4. **Site config description** — emphasize pretrained model wording in shortDescription/description.
5. **SEO absolute URLs** — do not concatenate `NEXT_PUBLIC_BASE_PATH` onto `NEXT_PUBLIC_SITE_URL` (avoids `/hackernewsreport/hackernewsreport/...` in sitemap/robots/OG).

## No change required

- Engineering M1 table and M3 cycle caveats already accurate.
- Under-the-hood schema_version=6 and story_report_state corrections already present.
- Footer / demo snapshot disclosures already accurate.

## External link targets (release)

- GitHub repo: https://github.com/sjyu0423/hackernewsreport
- Milestone docs on `milestone-4-2-production-reliability` branch (public GitHub blob URLs)
- Demo story `source_url` values are http(s) only from fixture
