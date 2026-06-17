import { Check } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { pricingTiers } from "@/lib/content";
import { cn } from "@/lib/utils";

export function PricingCards() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      {pricingTiers.map((tier) => (
        <div
          key={tier.name}
          className={cn(
            "relative flex flex-col rounded-2xl border p-8 transition-all",
            tier.highlighted
              ? "border-primary/60 bg-card shadow-xl shadow-primary/10 lg:-translate-y-2"
              : "border-border bg-card",
          )}
        >
          {tier.highlighted && (
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-[linear-gradient(100deg,var(--color-brand-1),var(--color-brand-2))] px-3 py-1 text-xs font-semibold text-white">
              Most popular
            </span>
          )}
          <h3 className="text-lg font-semibold">{tier.name}</h3>
          <div className="mt-4 flex items-baseline gap-1">
            <span className="text-4xl font-bold tracking-tight">{tier.price}</span>
            {tier.period && <span className="text-sm text-muted-foreground">{tier.period}</span>}
          </div>
          <p className="mt-3 text-sm text-muted-foreground">{tier.description}</p>

          <ul className="mt-6 flex-1 space-y-3">
            {tier.features.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                <span>{f}</span>
              </li>
            ))}
          </ul>

          <Button
            asChild
            className="mt-8"
            variant={tier.highlighted ? "gradient" : "outline"}
            size="lg"
          >
            <Link href={tier.href}>{tier.cta}</Link>
          </Button>
        </div>
      ))}
    </div>
  );
}
