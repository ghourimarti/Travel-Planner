import { redirect } from "next/navigation";

import { AppShell } from "@/components/app/app-shell";
import { authMode, getCurrentUser, logoutPath } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // Fail-closed: no session, no app. Redirects to Auth0 or the dev login.
  // Note: we intentionally DON'T pass the user object to the client shell, so no
  // PII (email) is serialized into the page payload.
  const user = await getCurrentUser();
  if (!user) redirect(authMode === "auth0" ? "/auth/login?returnTo=/app" : "/login");

  return (
    <AppShell mode={authMode} logoutHref={logoutPath}>
      {children}
    </AppShell>
  );
}
