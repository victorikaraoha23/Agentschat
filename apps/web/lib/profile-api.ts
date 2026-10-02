/**
 * Profile request against the AgentsChat API (`GET /me`) — Task 3.3.
 *
 * The browser asks the backend for the signed-in user's AgentsChat profile.
 * The backend derives the identity from the token it verifies, so this module
 * only forwards the session's access token; it never sends a user id, and the
 * token is never stored, rendered, or logged.
 *
 * Like `app/health-api.ts`, nothing here throws: every failure is a typed
 * result carrying a fixed message of our own, so raw server bodies and error
 * objects never reach the UI.
 */

import { getAccessToken } from "./auth.ts";
import { API_BASE_URL } from "./api-base-url.ts";

/** The profile as the API returns it (snake_case JSON). */
interface ProfilePayload {
  user_id: string;
  created_at: string;
  updated_at: string;
}

/** The profile as this application uses it. */
export interface UserProfile {
  userId: string;
  createdAt: string;
  updatedAt: string;
}

/** Why a profile request failed. */
export type ProfileFailureReason =
  | "unauthenticated"
  | "network"
  | "http"
  | "invalid-response"
  | "unexpected";

export type ProfileResult =
  | { ok: true; profile: UserProfile }
  | { ok: false; reason: ProfileFailureReason; message: string; statusCode?: number };

const UNREADABLE_SESSION_MESSAGE = "Your profile could not be loaded: sign in again.";
const REJECTED_MESSAGE = "Your profile could not be loaded: your session is not valid.";
const UNEXPECTED_MESSAGE = "An unexpected error occurred while loading your profile.";
const PROFILE_TIMEOUT_MS = 5_000;

type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

const defaultFetch: FetchLike = (url, init) => fetch(url, init);

/** Request options; both fields exist so tests never touch the network or Supabase. */
export interface ProfileRequestOptions {
  /** Session access token. Omit to read it from the current session. */
  accessToken?: string | null;
  fetchImpl?: FetchLike;
}

function toProfile(payload: ProfilePayload): UserProfile {
  return {
    userId: payload.user_id,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  };
}

function isProfilePayload(body: unknown): body is ProfilePayload {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  // Narrow with `in` checks rather than asserting a shape onto unknown.
  if (!("user_id" in body) || typeof body.user_id !== "string") {
    return false;
  }
  if (!("created_at" in body) || typeof body.created_at !== "string") {
    return false;
  }
  return "updated_at" in body && typeof body.updated_at === "string";
}

/**
 * Request `GET /me` with the session's access token and classify the outcome.
 *
 * Only the bearer token is sent — never a user id — because the API derives
 * the identity from the token it verifies. The function never throws.
 */
export async function fetchMyProfile(
  options: ProfileRequestOptions = {},
): Promise<ProfileResult> {
  const token =
    options.accessToken !== undefined ? options.accessToken : await getAccessToken();
  if (token === null || token === "") {
    return {
      ok: false,
      reason: "unauthenticated",
      message: UNREADABLE_SESSION_MESSAGE,
    };
  }

  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const url = `${API_BASE_URL.replace(/\/+$/, "")}/me`;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), PROFILE_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetchImpl(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
    } catch {
      return controller.signal.aborted
        ? { ok: false, reason: "network", message: "Loading your profile timed out." }
        : { ok: false, reason: "network", message: "Request failed." };
    }

    if (response.status === 401 || response.status === 403) {
      return {
        ok: false,
        reason: "unauthenticated",
        message: REJECTED_MESSAGE,
        statusCode: response.status,
      };
    }
    if (!response.ok) {
      return {
        ok: false,
        reason: "http",
        message: `The API responded with HTTP ${response.status}.`,
        statusCode: response.status,
      };
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      if (controller.signal.aborted) {
        return { ok: false, reason: "network", message: "Loading your profile timed out." };
      }
      return {
        ok: false,
        reason: "invalid-response",
        message: "The API response was not valid JSON.",
      };
    }

    if (!isProfilePayload(body)) {
      return {
        ok: false,
        reason: "invalid-response",
        message: "The API response did not contain a profile.",
      };
    }

    return { ok: true, profile: toProfile(body) };
  } catch {
    // Anything unclassified stays a safe, fixed message rather than raw text.
    return { ok: false, reason: "unexpected", message: UNEXPECTED_MESSAGE };
  } finally {
    clearTimeout(deadline);
  }
}
