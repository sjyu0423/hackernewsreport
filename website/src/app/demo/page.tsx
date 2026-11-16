import type { Metadata } from "next";
import { DemoExplorer } from "@/components/DemoExplorer";
import { PageHero } from "@/components/PageHero";
import { demoSnapshot, getDemoStories } from "@/lib/demo";

export const metadata: Metadata = {
  title: "Demo",
  description:
    "Interactive QwenNews briefing demo powered by a fixed snapshot of real local Qwen3 4B analyses — not live inference.",
};

export default function DemoPage() {
  const stories = getDemoStories();

  return (
    <div className="shell space-y-10 pb-20">
      <PageHero
        eyebrow="Demo"
        title="Interactive news briefing"
        description="Browse a fixed snapshot of real QwenNews analyses. Filter by category, sort by scores, and expand stories for why-it-matters and evidence details."
      />
      <DemoExplorer
        stories={stories}
        snapshotId={demoSnapshot.snapshot_id}
        recordedAt={demoSnapshot.recorded_at}
        disclaimer={demoSnapshot.disclaimer}
        modelId={demoSnapshot.model_id}
        quantization={demoSnapshot.model_quantization}
      />
    </div>
  );
}
