import { Mail, MessageSquare, Phone } from "lucide-react";
import type { Metadata } from "next";

import { ContactForm } from "@/components/marketing/contact-form";

export const metadata: Metadata = {
  title: "Contact",
  description: "Talk to the Voyantra team about Pro, Enterprise, or partnerships.",
};

const channels = [
  { icon: Mail, label: "Email", value: "hello@voyantra.app" },
  { icon: MessageSquare, label: "Sales", value: "sales@voyantra.app" },
  { icon: Phone, label: "Support", value: "Mon–Fri, 9–6 CET" },
];

export default function ContactPage() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="grid gap-12 lg:grid-cols-2">
        <div>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Let&apos;s talk</h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Questions about Voyantra, the API, or an enterprise rollout? We usually reply within a
            business day.
          </p>
          <ul className="mt-10 space-y-6">
            {channels.map((c) => (
              <li key={c.label} className="flex items-start gap-4">
                <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <c.icon className="size-5" />
                </span>
                <div>
                  <p className="text-sm font-medium">{c.label}</p>
                  <p className="text-sm text-muted-foreground">{c.value}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-border bg-card p-8 shadow-sm">
          <ContactForm />
        </div>
      </div>
    </section>
  );
}
