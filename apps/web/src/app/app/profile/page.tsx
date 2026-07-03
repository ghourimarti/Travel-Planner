import { Crown, Mail, Settings, Sparkles, User } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { TripStats } from "@/components/app/trip-stats";
import { Button } from "@/components/ui/button";
import { getCurrentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Your profile" };

export default async function ProfilePage() {
  const user = await getCurrentUser();
  const email = user?.email ?? "";
  const displayName =
    user?.name && !user.name.includes("@") ? user.name : email ? email.split("@")[0] : "Traveler";

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl border border-border bg-card p-8">
        <div className="pointer-events-none absolute -right-10 -top-10 size-48 rounded-full bg-[radial-gradient(circle,var(--color-brand-1),transparent_60%)] opacity-20 blur-2xl" />
        <div className="flex flex-col items-start gap-5 sm:flex-row sm:items-center">
          <div className="flex size-20 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,var(--color-brand-1),var(--color-brand-2))] text-white shadow-lg">
            <User className="size-9" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-2xl font-bold tracking-tight capitalize">{displayName}</h1>
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                <Sparkles className="size-3" /> Free plan
              </span>
            </div>
            {email && (
              <p className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                <Mail className="size-3.5" /> {email}
              </p>
            )}
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/app/settings">
                <Settings className="size-4" /> Settings
              </Link>
            </Button>
            <Button asChild variant="gradient" size="sm">
              <Link href="/pricing">
                <Crown className="size-4" /> Upgrade
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Your travel activity</h2>
        <TripStats />
      </section>

      <section className="rounded-2xl border border-border bg-card p-6">
        <h2 className="text-lg font-semibold">Account</h2>
        <dl className="mt-4 divide-y divide-border text-sm">
          <div className="flex items-center justify-between py-3">
            <dt className="text-muted-foreground">Name</dt>
            <dd className="font-medium capitalize">{displayName}</dd>
          </div>
          <div className="flex items-center justify-between py-3">
            <dt className="text-muted-foreground">Email</dt>
            <dd className="font-medium">{email || "—"}</dd>
          </div>
          <div className="flex items-center justify-between py-3">
            <dt className="text-muted-foreground">Plan</dt>
            <dd className="font-medium">Free</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
