import type { Metadata } from "next";

import { CTA } from "@/components/marketing/cta";

export const metadata: Metadata = {
  title: "About",
  description: "Why Voyantra exists: trustworthy, grounded AI travel planning.",
};

export default function AboutPage() {
  return (
    <>
      <section className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          We&apos;re building travel AI you can <span className="text-gradient">trust</span>.
        </h1>
        <div className="prose prose-neutral mt-8 max-w-none text-muted-foreground dark:prose-invert">
          <p className="text-lg leading-relaxed">
            Most AI trip planners confidently invent places that don&apos;t exist. Voyantra was
            built on a different premise: an itinerary is only useful if every place on it is real,
            well-located, and checked.
          </p>
          <p className="mt-6 leading-relaxed">
            To get there, we treat planning as a multi-agent problem. A coordinator dispatches
            per-city worker agents that geocode destinations, gather points of interest from
            OpenStreetMap, pull live weather and routing, and draft a plan. A dedicated critic agent
            then reviews each draft and sends it back for correction if it finds an invented place or
            a gap — before you ever see it.
          </p>
          <p className="mt-6 leading-relaxed">
            The result is grounded, transparent planning: you watch the agents work in real time,
            and every recommendation traces back to real-world data.
          </p>
        </div>

        <h2 id="careers" className="mt-16 text-2xl font-bold tracking-tight">
          Careers
        </h2>
        <p className="mt-4 text-muted-foreground">
          We&apos;re a small team obsessed with grounded AI and great travel. If that resonates,
          reach out via our contact page — we&apos;d love to hear from you.
        </p>
      </section>
      <CTA />
    </>
  );
}
