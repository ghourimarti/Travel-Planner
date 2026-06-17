import { Bot, CloudSun, Gauge, MapPin, Route, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { features } from "@/lib/content";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  Bot,
  MapPin,
  CloudSun,
  Route,
  ShieldCheck,
  Gauge,
};

export function FeatureGrid({ className }: { className?: string }) {
  return (
    <section className={cn("mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8", className)}>
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
          Everything you need to plan with confidence
        </h2>
        <p className="mt-4 text-lg text-muted-foreground">
          Voyantra isn&apos;t a single prompt. It&apos;s a production multi-agent system built for
          grounded, trustworthy travel planning.
        </p>
      </div>

      <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {features.map((f) => {
          const Icon = ICONS[f.icon] ?? Bot;
          return (
            <div
              key={f.title}
              className="group rounded-xl border border-border bg-card p-6 transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-lg"
            >
              <div className="flex size-11 items-center justify-center rounded-lg bg-[linear-gradient(135deg,var(--color-brand-1),var(--color-brand-2))] text-white shadow-sm">
                <Icon className="size-5" />
              </div>
              <h3 className="mt-5 text-lg font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.body}</p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
