/**
 * Auth0 client — guarded so the app builds and runs KEYLESS.
 *
 * The Auth0Client validates its config eagerly; if the Auth0 env block isn't set
 * (local dev), we keep `auth0 = null` and the whole app degrades to dev mode
 * instead of crashing. When configured, the middleware mounts /auth/* routes and
 * the BFF attaches the access token to backend calls.
 */
import { Auth0Client } from "@auth0/nextjs-auth0/server";

/**
 * Does the BACKEND actually verify access tokens?
 *
 * Mirrors `tp_core.settings.Settings.auth_required` exactly — explicit flag when set,
 * otherwise "enforced everywhere except app_env == local" — so the two tiers can never
 * disagree about whether a token means anything.
 */
function backendVerifiesTokens(): boolean {
  const flag = process.env.AUTH_ENABLED;
  if (flag !== undefined && flag !== "") return flag.toLowerCase() === "true";
  return process.env.APP_ENV !== "local";
}

function buildClient(): Auth0Client | null {
  const { AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_SECRET, APP_BASE_URL } =
    process.env;
  if (!AUTH0_DOMAIN || !AUTH0_CLIENT_ID || !AUTH0_CLIENT_SECRET || !AUTH0_SECRET || !APP_BASE_URL) {
    return null;
  }
  try {
    return new Auth0Client({
      authorizationParameters: {
        // Ask for an API access token ONLY when something will verify it.
        //
        // Requesting an `audience` makes Auth0 show its "Authorize App" consent screen,
        // and Auth0 cannot skip that screen for an app served from localhost — it has no
        // way to verify the app's identity there. Because `backendAuthHeader()` runs on
        // EVERY backend call, that consent appeared on every trip the user planned,
        // authorising a token the API was not checking at all (AUTH_ENABLED=false).
        //
        // Dropping the audience when auth is off leaves login fully working (Auth0 still
        // issues an ID token and a session); it only stops requesting a credential that
        // nothing consumes. When auth IS enforced the audience comes back automatically —
        // and a real deployment is not localhost, so Auth0 can skip consent there once
        // "Allow Skipping User Consent" is enabled on the API.
        ...(backendVerifiesTokens() ? { audience: process.env.AUTH0_AUDIENCE } : {}),
        // `offline_access` asks for a REFRESH token, which Auth0 also treats as
        // consent-requiring — and on localhost that consent can never be remembered,
        // so it reappears on every authorize. A refresh token exists to renew an API
        // access token; with no audience requested there is no access token to renew,
        // so locally it is a consent prompt bought for nothing. The Auth0 SDK keeps its
        // own encrypted session cookie either way, so login and the session are
        // unaffected. AUTH0_SCOPE still overrides, for anyone who wants it back.
        scope:
          process.env.AUTH0_SCOPE ??
          (backendVerifiesTokens()
            ? "openid profile email offline_access"
            : "openid profile email"),
      },
    });
  } catch {
    return null;
  }
}

export const auth0 = buildClient();

/** Whether real Auth0 login is wired (env present). UI uses this to pick its mode. */
export const authConfigured = auth0 !== null;

export interface SessionUser {
  sub?: string;
  name?: string;
  email?: string;
  picture?: string;
}

/** Current user or null — never throws, even when Auth0 is unconfigured. */
export async function getSessionUser(): Promise<SessionUser | null> {
  if (!auth0) return null;
  try {
    const session = await auth0.getSession();
    return (session?.user as SessionUser | undefined) ?? null;
  } catch (err) {
    // NOT swallowed silently any more. `app/layout.tsx` redirects to /auth/login
    // whenever this returns null, so a session that cannot be READ is
    // indistinguishable from "not logged in" — you get bounced to Auth0 on every
    // navigation, and on localhost Auth0 cannot skip its consent screen, so the
    // "Authorize App" dialog reappears forever with nothing explaining why.
    // A failure this consequential must leave a trace: `docker logs
    // p3-ai-travel-planner-web-1 | grep auth0-session`.
    console.warn("[auth0-session] could not read the session:", err);
    return null;
  }
}

/** Bearer header for backend calls, or {} when not logged in / not configured. */
export async function backendAuthHeader(): Promise<Record<string, string>> {
  if (!auth0) return {};
  try {
    const { token } = await auth0.getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}
