import { Quote } from "lucide-react";

import { testimonials } from "@/lib/content";

export function Testimonials() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Loved by travel teams</h2>
        <p className="mt-4 text-lg text-muted-foreground">
          From solo trip planning to embedded enterprise workflows.
        </p>
      </div>

      <div className="mt-14 grid gap-6 lg:grid-cols-3">
        {testimonials.map((t) => (
          <figure
            key={t.name}
            className="flex flex-col rounded-xl border border-border bg-card p-6 shadow-sm"
          >
            <Quote className="size-7 text-primary/40" />
            <blockquote className="mt-4 flex-1 text-sm leading-relaxed">{t.quote}</blockquote>
            <figcaption className="mt-6 border-t border-border pt-4">
              <p className="text-sm font-semibold">{t.name}</p>
              <p className="text-xs text-muted-foreground">{t.role}</p>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
