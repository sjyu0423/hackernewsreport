import Link from "next/link";

export default function NotFound() {
  return (
    <div className="shell flex min-h-[60vh] flex-col items-start justify-center gap-5 py-20">
      <p className="eyebrow">404</p>
      <h1 className="text-4xl sm:text-5xl">Page not found</h1>
      <p className="max-w-md text-muted">
        That route is not part of the public QwenNews site. Head home or open
        one of the foundation sections.
      </p>
      <Link href="/" className="btn-primary no-underline">
        Back to home
      </Link>
    </div>
  );
}
