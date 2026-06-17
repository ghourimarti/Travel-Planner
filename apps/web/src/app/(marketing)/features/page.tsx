import type { Metadata } from "next";

import { CTA } from "@/components/marketing/cta";
import { FeatureGrid } from "@/components/marketing/feature-grid";
import { HowItWorks } from "@/components/marketing/how-it-works";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Multi-agent planning, real-place grounding, live weather & routing, a critic that catches invented places, and hard cost controls.",
};

export default function FeaturesPage() {
  return (
    <>
      <section className="mx-auto max-w-7xl px-4 pt-20 text-center sm:px-6 lg:px-8">
        <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
          A production multi-agent engine for{" "}
          <span className="text-gradient">grounded travel planning</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          Every Voyantra itinerary is built by a supervised team of agents and validated against
          real-world data before it reaches you.
        </p>
      </section>
      <FeatureGrid />
      <HowItWorks />
      <CTA />
    </>
  );
}
