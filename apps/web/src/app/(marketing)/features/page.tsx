import type { Metadata } from "next";

import { CTA } from "@/components/marketing/cta";
import { FeatureGrid } from "@/components/marketing/feature-grid";
import { HowItWorks } from "@/components/marketing/how-it-works";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Complete trips in seconds — real places only, planned around the weather, effortless multi-city routes, and every plan double-checked before you see it.",
};

export default function FeaturesPage() {
  return (
    <>
      <section className="mx-auto max-w-7xl px-4 pt-20 text-center sm:px-6 lg:px-8">
        <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
          Everything you need for a <span className="text-gradient">trip you can trust</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          Every Voyantra itinerary is built from real places and double-checked before it reaches
          you — so you can plan with total confidence.
        </p>
      </section>
      <FeatureGrid />
      <HowItWorks />
      <CTA />
    </>
  );
}
