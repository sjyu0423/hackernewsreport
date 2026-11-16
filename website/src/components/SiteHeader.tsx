"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { primaryNav, siteConfig } from "@/lib/site";

function normalizePath(pathname: string): string {
  if (pathname.length > 1 && pathname.endsWith("/")) {
    return pathname.slice(0, -1);
  }
  return pathname || "/";
}

function isActive(pathname: string, href: string): boolean {
  const current = normalizePath(pathname);
  const target = normalizePath(href);
  if (target === "/") {
    return current === "/";
  }
  return current === target || current.startsWith(`${target}/`);
}

export function SiteHeader() {
  const pathname = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  const menuId = useId();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <header className="sticky top-0 z-50 border-b border-line/80 bg-ink/80 backdrop-blur-md">
      <div className="shell flex h-[var(--header-h)] items-center justify-between gap-4">
        <Link
          href="/"
          className="group flex min-w-0 flex-col text-paper no-underline hover:text-paper"
          aria-label={`${siteConfig.name} home`}
        >
          <span className="font-display text-xl tracking-tight sm:text-2xl">
            {siteConfig.name}
          </span>
          <span className="truncate text-xs text-muted group-hover:text-muted">
            Public project site
          </span>
        </Link>

        <nav
          className="hidden items-center gap-1 lg:flex"
          aria-label="Primary"
        >
          {primaryNav.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-lg px-3 py-2 text-sm no-underline transition-colors ${
                  active
                    ? "bg-accent-soft text-paper"
                    : "text-muted hover:bg-ink-soft hover:text-paper"
                }`}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <button
          type="button"
          className="btn-secondary lg:hidden"
          aria-expanded={open}
          aria-controls={menuId}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Close" : "Menu"}
        </button>
      </div>

      <div
        id={menuId}
        hidden={!open}
        className="border-t border-line bg-ink-elevated lg:hidden"
      >
        <nav className="shell flex flex-col gap-1 py-3" aria-label="Mobile">
          {primaryNav.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-lg px-3 py-3 no-underline ${
                  active
                    ? "bg-accent-soft text-paper"
                    : "text-muted hover:bg-ink-soft hover:text-paper"
                }`}
                aria-current={active ? "page" : undefined}
              >
                <span className="block text-sm font-medium">{item.label}</span>
                <span className="block text-xs text-muted">{item.description}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
