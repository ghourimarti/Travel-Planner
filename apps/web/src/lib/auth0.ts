/**
 * Auth0 client (S13a, Decision 9) — guarded so the app builds and runs KEYLESS.
 *
 * The Auth0Client validates its config eagerly; if the Auth0 env block isn't set
 * (local dev), we keep `auth0 = null` and the whole app degrades to dev mode
 * instead of crashing. When configured, the middleware mounts /auth/* routes and
 * the BFF attaches the access token to backend calls.
 */
import { Auth0Client } from "@auth0/nextjs-auth0/server";

function buildClient(): Auth0Client | null {
  const { AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_SECRET, APP_BASE_URL } =
    process.env;
  if (!AUTH0_DOMAIN || !AUTH0_CLIENT_ID || !AUTH0_CLIENT_SECRET || !AUTH0_SECRET || !APP_BASE_URL) {
    return null;
  }
  try {
    return new Auth0Client({
      authorizationParameters: {
        audience: process.env.AUTH0_AUDIENCE,
        scope: process.env.AUTH0_SCOPE ?? "openid profile email offline_access",
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
  } catch {
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
