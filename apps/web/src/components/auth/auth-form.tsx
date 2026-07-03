"use client";

import { Loader2, LogIn, UserPlus } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type Mode = "signin" | "signup";

const OAUTH_ERRORS: Record<string, string> = {
  google_unavailable: "Google sign-in isn't set up yet. Use your email and password.",
  google_state: "That Google sign-in expired or didn't match. Please try again.",
  google_failed: "We couldn't sign you in with Google. Please try again.",
};

export function AuthForm({
  defaultMode = "signin",
  googleEnabled = false,
}: {
  defaultMode?: Mode;
  googleEnabled?: boolean;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [mode, setMode] = React.useState<Mode>(defaultMode);
  const [firstName, setFirstName] = React.useState("");
  const [lastName, setLastName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");
  const [error, setError] = React.useState<string | null>(
    () => OAUTH_ERRORS[params.get("error") ?? ""] ?? null,
  );
  const [loading, setLoading] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "signup" && password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setLoading(true);
    try {
      const endpoint = mode === "signup" ? "/api/dev-signup" : "/api/dev-login";
      const body =
        mode === "signup"
          ? { name: `${firstName} ${lastName}`.trim(), email, password }
          : { email, password };
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error ?? "Something went wrong.");
      }
      router.push("/app");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }

  return (
    <div>
      <Tabs
        value={mode}
        onValueChange={(v) => {
          setMode(v as Mode);
          setError(null);
        }}
      >
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="signin">Sign in</TabsTrigger>
          <TabsTrigger value="signup">Create account</TabsTrigger>
        </TabsList>
      </Tabs>

      {googleEnabled && (
        <>
          <a
            href={`/api/auth/google/start`}
            className="mt-6 flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted"
          >
            <GoogleIcon /> Continue with Google
          </a>
          <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground">
            <span className="h-px flex-1 bg-border" />
            OR
            <span className="h-px flex-1 bg-border" />
          </div>
        </>
      )}

      <form onSubmit={onSubmit} className={googleEnabled ? "space-y-4" : "mt-6 space-y-4"}>
        {mode === "signup" && (
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="firstName">First name</Label>
              <Input
                id="firstName"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Ada"
                required
                autoComplete="given-name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lastName">Last name</Label>
              <Input
                id="lastName"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Lovelace"
                required
                autoComplete="family-name"
              />
            </div>
          </div>
        )}
        <div className="space-y-2">
          <Label htmlFor="email">Email address</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            required
            autoComplete="email"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
          />
        </div>
        {mode === "signup" && (
          <div className="space-y-2">
            <Label htmlFor="confirm">Confirm password</Label>
            <Input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="new-password"
            />
          </div>
        )}

        {error && (
          <p className="rounded-lg border border-red-500/30 bg-red-500/5 px-3 py-2 text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}

        <Button type="submit" variant="gradient" size="lg" className="w-full" disabled={loading}>
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />{" "}
              {mode === "signup" ? "Creating account…" : "Signing in…"}
            </>
          ) : mode === "signup" ? (
            <>
              <UserPlus className="size-4" /> Create account
            </>
          ) : (
            <>
              <LogIn className="size-4" /> Sign in
            </>
          )}
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-muted-foreground">
        {mode === "signup"
          ? "By creating an account you agree to our Terms and Privacy Policy."
          : "Trouble signing in? Contact support and we'll help you get back in."}
      </p>
    </div>
  );
}

/** Inline, self-contained Google "G" mark (no external asset). */
function GoogleIcon() {
  return (
    <svg className="size-4" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1Z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"
      />
    </svg>
  );
}
