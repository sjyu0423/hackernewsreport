import Link from "next/link";
import { primaryNav, siteConfig } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line/80 bg-ink-elevated/40">
      <div className="shell grid gap-10 py-12 md:grid-cols-[1.4fr_1fr]">
        <div className="space-y-3">
          <p className="font-display text-2xl text-paper">{siteConfig.name}</p>
          <p className="max-w-md text-sm leading-relaxed text-muted">
            {siteConfig.tagline} This public site is a static project overview.
            It is separate from the private local dashboard and does not call
            Ollama, FastAPI, or SQLite at runtime.
          </p>
        </div>
        <div>
          <p className="eyebrow mb-3">Sections</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {primaryNav.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className="text-sm text-muted no-underline hover:text-paper"
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="border-t border-line/60">
        <div className="shell flex flex-col gap-2 py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>Local AI news reporting · pretrained Qwen3 4B via Ollama</p>
          <p>W0 foundation · static export · GitHub Pages ready</p>
        </div>
      </div>
    </footer>
  );
}
