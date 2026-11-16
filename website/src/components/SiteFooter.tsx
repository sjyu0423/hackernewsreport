import Link from "next/link";
import { primaryNav, siteConfig } from "@/lib/site";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-line/80 bg-ink-elevated/40">
      <div className="shell grid gap-10 py-12 md:grid-cols-[1.4fr_1fr_0.9fr]">
        <div className="space-y-3">
          <p className="font-display text-2xl text-paper">{siteConfig.name}</p>
          <p className="max-w-md text-sm leading-relaxed text-muted">
            {siteConfig.tagline} {siteConfig.supportLine} This public site is a
            static demonstration, separate from the private local dashboard.
          </p>
        </div>
        <div>
          <p className="eyebrow mb-3">Sections</p>
          <ul className="grid gap-2 sm:grid-cols-2 md:grid-cols-1">
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
        <div>
          <p className="eyebrow mb-3">Project</p>
          <ul className="space-y-2">
            <li>
              <a
                href={siteConfig.githubUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-muted no-underline hover:text-paper"
              >
                GitHub repository
              </a>
            </li>
            <li>
              <Link
                href="/how-it-works/"
                className="text-sm text-muted no-underline hover:text-paper"
              >
                Technical explanation
              </Link>
            </li>
            <li>
              <Link
                href="/engineering/"
                className="text-sm text-muted no-underline hover:text-paper"
              >
                Engineering evidence
              </Link>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-line/60">
        <div className="shell flex flex-col gap-2 py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <p>Local AI news reporting · pretrained Qwen3 4B via Ollama</p>
          <p>Static export · fixed demo snapshot · not live inference</p>
        </div>
      </div>
    </footer>
  );
}
