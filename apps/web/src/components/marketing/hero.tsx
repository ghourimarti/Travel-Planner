import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";

import { HeroDemo } from "@/components/marketing/hero-demo";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <section className="relative overflow-hidden">
      {/* aurora background */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-grid opacity-40" />
      <div className="pointer-events-none absolute -top-40 left-1/2 -z-10 h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-[radial-gradient(circle,var(--color-brand-1),transparent_60%)] opacity-25 blur-3xl animate-aurora" />
      <div className="pointer-events-none absolute -top-20 right-0 -z-10 h-[28rem] w-[28rem] rounded-full bg-[radial-gradient(circle,var(--color-brand-3),transparent_60%)] opacity-20 blur-3xl animate-aurora" />

      <div className="mx-auto grid max-w-7xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:gap-8 lg:px-8 lg:py-28">
        <div className="animate-float-up">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1 text-xs font-medium text-muted-foreground">
            <Sparkles className="size-3.5 text-primary" />
            Multi-agent planning, grounded in the real world
          </div>

          <h1 className="mt-6 text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
            Plan <span className="text-gradient">extraordinary trips</span> in seconds.
          </h1>

          <p className="mt-6 max-w-xl text-lg text-muted-foreground">
            Voyantra orchestrates a team of AI agents to build multi-city itineraries from real
            places, live weather and routing — every recommendation checked, cited and mapped.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button asChild size="lg" variant="gradient">
              <Link href="/signup">
                Start planning free <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/features">See how it works</Link>
            </Button>
          </div>

          <p className="mt-6 text-sm text-muted-foreground">
            No credit card required · grounded itineraries · transparent agent trace
          </p>
        </div>

        <div className="lg:pl-8">
          <HeroDemo />
        </div>
      </div>
    </section>
  );
}
