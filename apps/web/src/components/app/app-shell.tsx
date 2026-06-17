"use client";

import { Compass, LayoutDashboard, MapPlus, Menu, Plane, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { Logo } from "@/components/site/logo";
import { ThemeToggle } from "@/components/site/theme-toggle";
import type { AuthMode } from "@/lib/auth";
import type { AppUser } from "@/lib/types";
import { cn } from "@/lib/utils";

const NAV = [
  { title: "Dashboard", href: "/app", icon: LayoutDashboard },
  { title: "Plan a trip", href: "/app/plan", icon: MapPlus },
  { title: "Trips", href: "/app/trips", icon: Plane },
];

export function AppShell({
  user,
  mode,
  logoutHref,
  children,
}: {
  user: AppUser | null;
  mode: AuthMode;
  logoutHref: string;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);

  const SidebarBody = (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5">
        <Link href="/" aria-label="Voyantra home">
          <Logo />
        </Link>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
            >
              <item.icon className="size-4.5" />
              {item.title}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-3">
        <Link
          href="/"
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted/60 hover:text-foreground"
        >
          <Compass className="size-4.5" />
          Back to site
        </Link>
        <div className="mt-2 flex items-center justify-between rounded-lg px-3 py-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{user?.name ?? "Account"}</p>
            <p className="truncate text-xs text-muted-foreground">
              {user?.email ?? (mode === "dev" ? "dev session" : "signed in")}
            </p>
          </div>
          <ThemeToggle />
        </div>
        <Link
          href={logoutHref}
          className="mt-1 block rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted/60 hover:text-foreground"
        >
          Sign out
        </Link>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen">
      {/* desktop sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-border bg-card/40 lg:block">
        <div className="sticky top-0 h-screen">{SidebarBody}</div>
      </aside>

      {/* mobile sidebar */}
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <aside className="absolute left-0 top-0 h-full w-64 border-r border-border bg-card">
            <button
              aria-label="Close menu"
              className="absolute right-3 top-4 text-muted-foreground"
              onClick={() => setOpen(false)}
            >
              <X className="size-5" />
            </button>
            {SidebarBody}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-16 items-center gap-3 border-b border-border px-4 lg:hidden">
          <button aria-label="Open menu" onClick={() => setOpen(true)}>
            <Menu className="size-6" />
          </button>
          <Logo />
        </div>

        {mode === "dev" && (
          <div className="border-b border-border bg-muted/40 px-4 py-2 text-center text-xs text-muted-foreground">
            Signed in with a dev session. Configure the Auth0 env block to switch to SSO.
          </div>
        )}

        <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
