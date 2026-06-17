import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern your use of Voyantra.",
};

export default function TermsPage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6 lg:px-8">
      <h1 className="text-4xl font-bold tracking-tight">Terms of Service</h1>
      <p className="mt-3 text-sm text-muted-foreground">Last updated: {new Date().getFullYear()}</p>

      <div className="mt-10 space-y-8 text-sm leading-relaxed text-muted-foreground">
        <section>
          <h2 className="text-lg font-semibold text-foreground">Use of service</h2>
          <p className="mt-2">
            Voyantra generates travel itineraries for informational purposes. While we ground every
            recommendation in real-world data, you are responsible for verifying details such as
            opening hours, availability and travel conditions before you rely on them.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-foreground">Acceptable use</h2>
          <p className="mt-2">
            Don&apos;t abuse the service, attempt to circumvent rate limits, or use it for unlawful
            purposes. Enterprise API usage is governed by your separate agreement.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-foreground">Liability</h2>
          <p className="mt-2">
            The service is provided &quot;as is.&quot; To the extent permitted by law, Voyantra is not
            liable for losses arising from reliance on generated itineraries.
          </p>
        </section>
        <section>
          <h2 className="text-lg font-semibold text-foreground">Changes</h2>
          <p className="mt-2">
            We may update these terms from time to time. Continued use after changes constitutes
            acceptance of the revised terms.
          </p>
        </section>
      </div>
    </article>
  );
}
