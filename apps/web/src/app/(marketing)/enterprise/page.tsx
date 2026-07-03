import { Building2, KeyRound, LineChart, Lock, ServerCog, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Enterprise",
  description:
    "Add instant, reliable trip planning to your own product — with single sign-on, team accounts, usage controls, your own inventory and dedicated support.",
};

const capabilities = [
  { icon: KeyRound, title: "Easy integration", body: "Add trip planning to your app or website with a clean, well-documented API — the same engine that powers Voyantra." },
  { icon: Lock, title: "Enterprise security & SSO", body: "Single sign-on and secure, verified access on every request, so only the right people ever get in." },
  { icon: Users, title: "Team & multi-tenant ready", body: "Keep every customer's trips, data and settings cleanly separated, with full account isolation." },
  { icon: LineChart, title: "Predictable billing & limits", body: "Set usage limits per account and keep spend predictable — no surprises on your bill." },
  { icon: ServerCog, title: "Your places & inventory", body: "Plan trips around your own destinations, hotels or attractions, not just public data." },
  { icon: Building2, title: "Reliability & support", body: "Dependable uptime, clear reporting, and a dedicated team to help you launch and scale." },
];

export default function EnterprisePage() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-grid opacity-30" />
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Bring effortless trip planning to <span className="text-gradient">your product</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
              Give your customers instant, reliable trip planning inside your own app or website —
              backed by enterprise security, easy integration and dedicated support.
            </p>
            <div className="mt-8 flex justify-center gap-3">
              <Button asChild size="lg" variant="gradient">
                <Link href="/contact">Talk to sales</Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/features">Explore features</Link>
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((c) => (
            <div key={c.title} className="rounded-xl border border-border bg-card p-6">
              <c.icon className="size-7 text-primary" />
              <h3 className="mt-4 text-lg font-semibold">{c.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{c.body}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
