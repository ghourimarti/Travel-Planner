import { CTA } from "@/components/marketing/cta";
import { FAQ } from "@/components/marketing/faq";
import { FeatureGrid } from "@/components/marketing/feature-grid";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { LogoCloud } from "@/components/marketing/logo-cloud";
import { PricingCards } from "@/components/marketing/pricing-cards";
import { StatsBand } from "@/components/marketing/stats-band";
import { Testimonials } from "@/components/marketing/testimonials";

export default function HomePage() {
  return (
    <>
      <Hero />
      <LogoCloud />
      <FeatureGrid />
      <HowItWorks />
      <StatsBand />
      <Testimonials />
      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Simple, transparent pricing
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Start free. Upgrade when you&apos;re planning more.
          </p>
        </div>
        <PricingCards />
      </section>
      <FAQ />
      <CTA />
    </>
  );
}
