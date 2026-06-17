import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthCard } from "@/components/auth/auth-card";
import { authMode, getCurrentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to Voyantra.",
};

export default async function LoginPage() {
  if (authMode === "auth0") redirect("/auth/login?returnTo=/app");
  const user = await getCurrentUser();
  if (user) redirect("/app");

  return (
    <AuthCard
      title="Welcome back"
      subtitle="Sign in to plan grounded, multi-city trips."
      defaultMode="signin"
    />
  );
}
