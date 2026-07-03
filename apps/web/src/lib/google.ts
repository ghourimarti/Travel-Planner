/**
 * "Continue with Google" for the native sign-in — a direct OAuth 2.0 authorization-code
 * flow that mints the app's OWN session (no third-party hosted page). Enabled only when
 * GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET are set, so the button auto-hides otherwise.
 */
import "server-only";

const AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth";
const TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token";

/** Whether the Google button should show (both credentials present). */
export const googleConfigured =
  Boolean(process.env.GOOGLE_CLIENT_ID) && Boolean(process.env.GOOGLE_CLIENT_SECRET);

/** Redirect URI Google calls back to — must be registered in the Google Cloud console. */
export function googleRedirectUri(): string {
  const base = process.env.APP_BASE_URL ?? "http://localhost:3006";
  return `${base.replace(/\/$/, "")}/api/auth/google/callback`;
}

/** Build the Google consent-screen URL for a given CSRF state. */
export function googleAuthUrl(state: string): string {
  const params = new URLSearchParams({
    client_id: process.env.GOOGLE_CLIENT_ID ?? "",
    redirect_uri: googleRedirectUri(),
    response_type: "code",
    scope: "openid email profile",
    state,
    access_type: "online",
    prompt: "select_account",
  });
  return `${AUTH_ENDPOINT}?${params.toString()}`;
}

export interface GoogleProfile {
  email: string;
  firstName: string;
  lastName: string;
  name: string;
}

/** Decode a JWT payload without verifying (the id_token comes straight from Google's
 *  token endpoint over TLS using our client secret — a trusted confidential-client channel). */
function decodeJwtPayload(jwt: string): Record<string, unknown> {
  const part = jwt.split(".")[1] ?? "";
  const json = Buffer.from(part, "base64url").toString("utf8");
  return JSON.parse(json) as Record<string, unknown>;
}

/** Exchange an authorization code for the signed-in Google profile, or null on failure. */
export async function exchangeCodeForProfile(code: string): Promise<GoogleProfile | null> {
  try {
    const res = await fetch(TOKEN_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: process.env.GOOGLE_CLIENT_ID ?? "",
        client_secret: process.env.GOOGLE_CLIENT_SECRET ?? "",
        redirect_uri: googleRedirectUri(),
        grant_type: "authorization_code",
      }),
    });
    if (!res.ok) return null;

    const data = (await res.json()) as { id_token?: string };
    if (!data.id_token) return null;

    const claims = decodeJwtPayload(data.id_token);
    const email = typeof claims.email === "string" ? claims.email : "";
    if (!email) return null;

    const firstName = typeof claims.given_name === "string" ? claims.given_name : "";
    const lastName = typeof claims.family_name === "string" ? claims.family_name : "";
    const name =
      typeof claims.name === "string" && claims.name
        ? claims.name
        : [firstName, lastName].filter(Boolean).join(" ") || email.split("@")[0];

    return { email, firstName, lastName, name };
  } catch {
    return null;
  }
}
