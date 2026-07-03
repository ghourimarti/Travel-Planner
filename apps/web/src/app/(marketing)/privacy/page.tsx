import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "How Voyantra handles your data.",
};

export default function PrivacyPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8">
      <h1 className="text-4xl font-bold tracking-tight">Privacy Policy</h1>
      <p className="mt-3 text-sm text-muted-foreground">Last updated: {new Date().getFullYear()}</p>

      <div className="mt-10 space-y-8 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="text-lg font-semibold text-foreground">Data we collect</h2>
          <p className="mt-2">
            We collect the minimum needed to plan your trips: the cities, interests and dates you
            submit, and account information when you sign in. We do not sell your data.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-foreground">How we use it</h2>
          <p className="mt-2">
            We use your planning requests to build your itineraries. We remove personal information
            from our logs and keep operational data only as long as necessary.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-foreground">Your rights</h2>
          <p className="mt-2">
            You can request export or deletion of your data at any time. Enterprise customers
            receive full tenant isolation and configurable retention.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-foreground">Contact</h2>
          <p className="mt-2">
            Questions about privacy? Email privacy@voyantra.app and we&apos;ll respond promptly.
          </p>
        </section>
      </div>
    </article>
  );
}
