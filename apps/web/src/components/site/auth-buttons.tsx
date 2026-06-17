import { LayoutDashboard, LogIn } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { AppUser } from "@/lib/types";

/** Sign-in / app-entry buttons driven by the unified auth layer. */
export function AuthButtons({
  user,
  loginHref,
  signupHref,
  logoutHref,
}: {
  user: AppUser | null;
  loginHref: string;
  signupHref: string;
  logoutHref: string;
}) {
  if (user) {
    return (
      <div className="flex items-center gap-2">
        <Button asChild variant="ghost" size="sm">
          <Link href={logoutHref}>Sign out</Link>
        </Button>
        <Button asChild variant="gradient" size="sm">
          <Link href="/app">
            <LayoutDashboard className="size-4" /> Dashboard
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Button asChild variant="ghost" size="sm">
        <Link href={loginHref}>Sign in</Link>
      </Button>
      <Button asChild variant="gradient" size="sm">
        <Link href={signupHref}>
          <LogIn className="size-4" /> Get started
        </Link>
      </Button>
    </div>
  );
}
