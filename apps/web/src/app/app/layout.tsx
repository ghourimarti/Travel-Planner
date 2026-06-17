import { redirect } from "next/navigation";

import { AppShell } from "@/components/app/app-shell";
import { authMode, getCurrentUser, logoutPath } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // Fail-closed: no session, no app. Redirects to Auth0 or the dev login.
  const user = await getCurrentUser();
  if (!user) redirect(authMode === "auth0" ? "/auth/login?returnTo=/app" : "/login");

  return (
    <AppShell user={user} mode={authMode} logoutHref={logoutPath}>
      {children}
    </AppShell>
  );
}
