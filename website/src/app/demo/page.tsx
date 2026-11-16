import type { Metadata } from "next";
import { ComingSoonPanel } from "@/components/ComingSoonPanel";
import { PageHero } from "@/components/PageHero";
import { publicFixtureNote } from "@/lib/site";

export const metadata: Metadata = {
  title: "Demo",
  description:
    "Interactive news briefing demonstration for QwenNews. W0 scaffolds the route; fixture-backed demo content arrives later.",
};

export default function DemoPage() {
  return (
    <div className="shell space-y-10 pb-20">
      <PageHero
        eyebrow="Demo"
        title="Interactive news briefing"
        description="A future static demonstration of how QwenNews turns public stories into a readable briefing — powered by fixtures, never by a live model call from this site."
      >
        <p className="status-chip" role="status">
          <span className="status-dot" aria-hidden="true" />
          Static demo · not live inference
        </p>
      </PageHero>

      <ComingSoonPanel
        milestone="W1"
        title="Briefing experience reserved"
        summary={publicFixtureNote}
        planned={[
          "Fixture-backed sample briefing UI",
          "Story cards with original public source URLs",
          "Explicit ‘recorded sample’ labeling",
          "Empty and loading states for demo interactions",
          "No Ollama / FastAPI / SQLite runtime connections",
        ]}
      />
    </div>
  );
}
