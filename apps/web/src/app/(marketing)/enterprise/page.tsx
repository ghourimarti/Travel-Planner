import { Building2, KeyRound, LineChart, Lock, ServerCog, Users } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Enterprise",
  description:
    "Embed Voyantra's multi-agent planning engine at scale with SSO, multi-tenancy, per-tenant quotas, audit logs and an SLA.",
};

const capabilities = [
  { icon: KeyRound, title: "API & SDK access", body: "The same engine our app uses, exposed via a clean REST API with higher rate limits." },
  { icon: Lock, title: "SSO & Auth0", body: "Enterprise SSO, JWT-verified access tokens, and fail-closed authorization on every request." },
  { icon: Users, title: "Multi-tenancy", body: "Strict per-tenant isolation across runs, retrieval ACLs and audit trails." },
  { icon: LineChart, title: "Quotas & cost controls", body: "Per-tenant quotas, rate limits and hard run budgets so spend is always predictable." },
  { icon: ServerCog, title: "Custom corpora", body: "Bring your own POI and content corpus to ground itineraries in your inventory." },
  { icon: Building2, title: "SLA & support", body: "99.5%+ uptime targets, observability you can audit, and dedicated support." },
];

export default function EnterprisePage() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-grid opacity-30" />
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Planning infrastructure for <span className="text-gradient">platforms at scale</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
              Voyantra Enterprise embeds grounded, multi-agent itinerary generation into your
              product — with the security, isolation and observability production demands.
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
