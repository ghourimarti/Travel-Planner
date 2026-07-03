"use client";

import {
  ChevronDown,
  Clock,
  Compass,
  Languages,
  LogOut,
  MapPlus,
  Menu,
  Plane,
  Settings,
  User,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { Logo } from "@/components/site/logo";
import { ThemeToggle } from "@/components/site/theme-toggle";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { AuthMode } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { title: "Home", href: "/" },
  { title: "Dashboard", href: "/app" },
  { title: "About", href: "/about" },
  { title: "Features", href: "/features" },
  { title: "Pricing", href: "/pricing" },
  { title: "Enterprise", href: "/enterprise" },
];

const TRIPS_MENU = [
  { title: "Explore", href: "/app/explore", icon: Compass, desc: "Discover destinations" },
  { title: "Plan a trip", href: "/app/plan", icon: MapPlus, desc: "Build a new itinerary" },
  { title: "My trips", href: "/app/trips", icon: Plane, desc: "Your saved itineraries" },
];

const ACCOUNT_MENU = [
  { title: "Your profile", href: "/app/profile", icon: User },
  { title: "Settings", href: "/app/settings", icon: Settings },
  { title: "Language", href: "/app/settings#language", icon: Languages },
  { title: "History", href: "/app/trips", icon: Clock },
];

function navActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/app") return pathname === "/app";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function tripsActive(pathname: string): boolean {
  return ["/app/explore", "/app/plan", "/app/trips"].some((p) => pathname.startsWith(p));
}

/** The single, consistent top navbar shown on every signed-in page (app + marketing). */
export function SiteHeader({ mode, logoutHref }: { mode: AuthMode; logoutHref: string }) {
  const pathname = usePathname();
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => setOpen(false), [pathname]);

  const linkCls = (active: boolean) =>
    cn(
      "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
      active
        ? "bg-primary/10 text-primary"
        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
    );

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/85 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-4">
          <Link href="/" aria-label="Voyantra home">
            <Logo />
          </Link>
          <nav className="hidden items-center gap-0.5 lg:flex">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className={linkCls(navActive(pathname, item.href))}>
                {item.title}
              </Link>
            ))}

            <div className="group/trips relative">
              <button className={cn("inline-flex items-center gap-1", linkCls(tripsActive(pathname)))}>
                Trips
                <ChevronDown className="size-4 transition-transform duration-200 group-hover/trips:rotate-180" />
              </button>
              <div className="invisible absolute left-0 top-full z-50 pt-2 opacity-0 transition-all duration-150 group-hover/trips:visible group-hover/trips:opacity-100 group-focus-within/trips:visible group-focus-within/trips:opacity-100">
                <div className="w-64 rounded-xl border border-border bg-popover p-1.5 shadow-xl">
                  {TRIPS_MENU.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted"
                    >
                      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <item.icon className="size-4.5" />
                      </span>
                      <span>
                        <span className="block text-sm font-medium">{item.title}</span>
                        <span className="block text-xs text-muted-foreground">{item.desc}</span>
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </nav>
        </div>

        <div className="hidden items-center gap-2 lg:flex">
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="flex size-9 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--color-brand-1),var(--color-brand-2))] text-white transition-transform hover:scale-105"
                aria-label="Account menu"
              >
                <User className="size-[18px]" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <p className="text-sm font-semibold">My account</p>
                <p className="text-xs text-muted-foreground">
                  {mode === "dev" ? "Dev session" : "Signed in"}
                </p>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {ACCOUNT_MENU.map((item) => (
                <DropdownMenuItem key={item.title} asChild>
                  <Link href={item.href}>
                    <item.icon /> {item.title}
                  </Link>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href={logoutHref}>
                  <LogOut /> Logout
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-center gap-1 lg:hidden">
          <ThemeToggle />
          <button
            aria-label="Toggle menu"
            onClick={() => setOpen((v) => !v)}
            className="inline-flex size-10 items-center justify-center rounded-md hover:bg-muted/60"
          >
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="max-h-[calc(100vh-4rem)] overflow-y-auto border-t border-border bg-background px-4 py-4 lg:hidden">
          <nav className="flex flex-col gap-0.5">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href} className={linkCls(navActive(pathname, item.href))}>
                {item.title}
              </Link>
            ))}
          </nav>
          <p className="mt-4 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Trips
          </p>
          <nav className="mt-1 flex flex-col gap-0.5">
            {TRIPS_MENU.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              >
                <item.icon className="size-4" /> {item.title}
              </Link>
            ))}
          </nav>
          <p className="mt-4 px-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Account
          </p>
          <nav className="mt-1 flex flex-col gap-0.5">
            {ACCOUNT_MENU.map((item) => (
              <Link
                key={item.title}
                href={item.href}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              >
                <item.icon className="size-4" /> {item.title}
              </Link>
            ))}
            <Link
              href={logoutHref}
              className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            >
              <LogOut className="size-4" /> Logout
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
