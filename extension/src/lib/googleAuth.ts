import constants from "@shared/constants.json";
import type { AuthVerifyResponse } from "@shared/types";

export class GoogleAuthError extends Error {}

/**
 * Runs the chrome.identity OAuth flow and returns an access token scoped to
 * the OAuth2 scopes declared in manifest.config.ts.
 */
export async function getGoogleAccessToken(interactive = true): Promise<string> {
  let result: chrome.identity.GetAuthTokenResult;
  try {
    result = await chrome.identity.getAuthToken({ interactive });
  } catch (err) {
    throw new GoogleAuthError(
      err instanceof Error ? err.message : "Google sign-in was cancelled or failed.",
    );
  }

  if (!result.token) {
    throw new GoogleAuthError("Google did not return an access token.");
  }

  return result.token;
}

export async function forgetGoogleAccessToken(token: string): Promise<void> {
  await chrome.identity.removeCachedAuthToken({ token });
}

/**
 * Confirms a Google access token with the backend before trusting it.
 */
export async function verifyTokenWithBackend(
  accessToken: string,
): Promise<AuthVerifyResponse> {
  const response = await fetch(`${constants.backendBaseUrl}${constants.authVerifyPath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: accessToken }),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new GoogleAuthError(body?.detail ?? `Backend rejected the token (${response.status}).`);
  }

  return response.json() as Promise<AuthVerifyResponse>;
}

/**
 * Runs the full connect flow: OAuth via chrome.identity, then verification
 * against the backend. On backend rejection, drops the cached token so the
 * next attempt re-prompts instead of retrying with the same bad token.
 */
export async function connectGoogleAccount(): Promise<AuthVerifyResponse> {
  const token = await getGoogleAccessToken(true);

  try {
    return await verifyTokenWithBackend(token);
  } catch (err) {
    await forgetGoogleAccessToken(token);
    throw err;
  }
}
