import type { Metadata } from "next";

import { CTA } from "@/components/marketing/cta";

export const metadata: Metadata = {
  title: "About",
  description: "Why Voyantra exists: trip planning you can actually trust, with real places only.",
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
            Most AI trip planners confidently suggest places that don&apos;t exist — restaurants
            that closed years ago, landmarks in the wrong city. Voyantra was built on a simple
            promise: every place on your itinerary should be real, easy to find, and worth your
            time.
          </p>
          <p className="mt-6 leading-relaxed">
            So we do the hard part for you. Voyantra researches your destinations, finds the places
            that fit what you love, checks the weather for your dates, and arranges each day to
            flow — then reviews the whole plan and fixes anything that doesn&apos;t hold up, before
            it ever reaches you.
          </p>
          <p className="mt-6 leading-relaxed">
            The result is a trip you can trust: real places, sensibly ordered, ready to go — and
            you can watch it all come together in seconds.
          </p>
        </div>

        <h2 id="careers" className="mt-16 text-2xl font-bold tracking-tight">
          Careers
        </h2>
        <p className="mt-4 text-muted-foreground">
          We&apos;re a small team obsessed with great travel and AI you can rely on. If that
          resonates, reach out via our contact page — we&apos;d love to hear from you.
        </p>
      </section>
      <CTA />
    </>
  );
}
