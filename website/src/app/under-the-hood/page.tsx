import type { Metadata } from "next";
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
        summary="W0 only establishes the route and navigation. Sensitive local paths, environment files, and production databases stay out of the public site."
        planned={[
          "Analysis JSON schema overview",
          "Story memory and watermark model",
          "Public-data export contract walkthrough",
          "What is intentionally not published",
        ]}
      />
    </div>
  );
}
