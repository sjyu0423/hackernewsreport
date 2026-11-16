import type { ReactNode } from "react";

type PageHeroProps = {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
};

export function PageHero({
  eyebrow,
  title,
  description,
  children,
}: PageHeroProps) {
  return (
    <header className="fade-rise space-y-5 border-b border-line/70 pb-10 pt-12 sm:pb-12 sm:pt-16">
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <h1 className="max-w-3xl text-4xl leading-[1.08] sm:text-5xl lg:text-6xl">
        {title}
      </h1>
      <p className="lede">{description}</p>
      {children ? <div className="fade-rise-delay pt-2">{children}</div> : null}
    </header>
  );
}
