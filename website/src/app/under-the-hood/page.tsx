import type { Metadata } from "next";
import Link from "next/link";
import { ComingSoonPanel } from "@/components/ComingSoonPanel";
import { PageHero } from "@/components/PageHero";

export const metadata: Metadata = {
  title: "Under the Hood",
  description:
    "Optional technical depth for QwenNews: schemas, prompts, storage, and operational details for curious engineers.",
};

export default function UnderTheHoodPage() {
  return (
    <div className="shell space-y-10 pb-20">
      <PageHero
        eyebrow="Under the Hood"
        title="Optional technical depth"
        description="For readers who want schemas, prompt contracts, storage details, and operational mechanics after the product story is clear."
      />

      <ComingSoonPanel
        milestone="W4–W5"
        title="Technical appendix reserved"
        summary="Architecture narrative now lives on How It Works. This page will later add schema/prompt appendices without publishing private paths or live databases."
        planned={[
          "Analysis JSON schema overview",
          "Story memory and watermark model",
          "Public-data export contract walkthrough",
          "What is intentionally not published",
        ]}
      />

      <p className="text-sm text-muted">
        Start with the{" "}
        <Link href="/how-it-works/" className="no-underline">
          interactive architecture
        </Link>{" "}
        explanation.
      </p>
    </div>
  );
}
