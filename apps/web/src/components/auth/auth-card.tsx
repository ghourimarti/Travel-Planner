import Link from "next/link";
import { Suspense } from "react";

import { AuthForm } from "@/components/auth/auth-form";
import { Logo } from "@/components/site/logo";
import { googleConfigured } from "@/lib/google";

export function AuthCard({
  title,
  subtitle,
  defaultMode,
}: {
  title: string;
  subtitle: string;
  defaultMode: "signin" | "signup";
}) {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-grid opacity-30" />
      <div className="pointer-events-none absolute left-1/2 top-0 -z-10 h-96 w-96 -translate-x-1/2 rounded-full bg-[radial-gradient(circle,var(--color-brand-1),transparent_60%)] opacity-20 blur-3xl animate-aurora" />

      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <Link href="/" aria-label="Voyantra home">
            <Logo />
          </Link>
        </div>
        <div className="rounded-2xl border border-border bg-card p-8 shadow-xl">
          <h1 className="text-center text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-2 text-center text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-8">
            <Suspense>
              <AuthForm defaultMode={defaultMode} googleEnabled={googleConfigured} />
            </Suspense>
          </div>
        </div>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          <Link href="/" className="hover:text-foreground">
            ← Back to site
          </Link>
        </p>
      </div>
    </main>
  );
}
