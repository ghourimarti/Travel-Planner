import type { Metadata } from "next";

import { FAQ } from "@/components/marketing/faq";
import { PricingCards } from "@/components/marketing/pricing-cards";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Start free, upgrade to Pro for unlimited planning, or go Enterprise for API access.",
};

export default function PricingPage() {
  return (
    <>
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto mb-14 max-w-2xl text-center">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Pricing that scales with you
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Transparent plans for travelers, businesses and platforms. No surprises.
          </p>
        </div>
        <PricingCards />
      </section>
      <FAQ />
    </>
  );
}
