import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AuthCard } from "@/components/auth/auth-card";
import { authMode, getCurrentUser } from "@/lib/auth";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create your Voyantra account.",
};

export default async function SignupPage() {
  if (authMode === "auth0") redirect("/auth/login?returnTo=/app&screen_hint=signup");
  const user = await getCurrentUser();
  if (user) redirect("/app");

  return (
    <AuthCard
      title="Create your account"
      subtitle="Start planning real, ready-to-go trips in seconds."
      defaultMode="signup"
    />
  );
}
