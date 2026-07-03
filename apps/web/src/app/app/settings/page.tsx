import type { Metadata } from "next";

import { SettingsForm } from "@/components/app/settings-form";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="mt-2 text-muted-foreground">
          Manage your preferences, language and notifications.
        </p>
      </header>
      <SettingsForm />
    </div>
  );
}
