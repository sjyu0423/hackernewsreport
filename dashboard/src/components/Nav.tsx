"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Today" },
  { href: "/hourly", label: "Hourly" },
  { href: "/stories", label: "Stories" },
  { href: "/history", label: "History" },
  { href: "/status", label: "Status" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <header className="topnav">
      <Link href="/" className="brand" aria-label="QwenNews home">
        Qwen<span>News</span>
      </Link>
      <nav className="nav-links" aria-label="Primary">
        {LINKS.map((link) => {
          const current =
            link.href === "/"
              ? pathname === "/"
              : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              aria-current={current ? "page" : undefined}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
