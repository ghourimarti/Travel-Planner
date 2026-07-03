import { SiteHeader } from "@/components/site/site-header";
import type { AuthMode } from "@/lib/auth";

export function AppShell({
  mode,
  logoutHref,
  children,
}: {
  mode: AuthMode;
  logoutHref: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader mode={mode} logoutHref={logoutHref} />

      {mode === "dev" && (
        <div className="border-b border-border bg-muted/40 px-4 py-2 text-center text-xs text-muted-foreground">
          Signed in with a dev session. Configure the Auth0 env block to switch to SSO.
        </div>
      )}

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
}
