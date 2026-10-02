/**
 * Authentication boundary for the web application (Task 3.2).
 *
 * The only module that talks to Supabase Auth: signup, login, logout, and
 * current-session detection. Pages and components call these functions instead
 * of the Supabase SDK, so provider details stay in one place.
 *
 * Session handling is delegated entirely to Supabase: `getSession()` reads the
 * session the SDK persists and refreshes it on its own. This module never
 * stores, caches, or renders an access token — it uses only the user id, the
 * email, and (for a single authenticated API call) the token of the session
 * Supabase already manages. There is no custom token system, no manual
 * credential storage, and no session database.
 *
 * Nothing here throws: every failure is a typed result with a fixed,
 * user-safe message. Raw provider errors never reach the UI or a log, and no
 * password is ever stored or logged.
 */

import { getSupabaseClient } from "./supabase-client.ts";

/** The parts of a Supabase auth error this boundary classifies by. */
export interface ClientAuthErrorLike {
  message: string;
  status?: number;
  code?: string;
}

/** The parts of a Supabase user this boundary uses. */
export interface ClientUserLike {
  id: string;
  /** Absent in the client type for some credential kinds, so treat it as optional. */
  email?: string | null;
}

/** The parts of a Supabase auth response this boundary uses. */
export interface ClientAuthResultLike {
  data: {
    user: ClientUserLike | null;
    session: { user: ClientUserLike } | null;
  };
  error: ClientAuthErrorLike | null;
}

/** The parts of Supabase's `getSession()` result this boundary uses. */
export interface ClientSessionResultLike {
  data: { session: { user: ClientUserLike; access_token?: string } | null };
  error: ClientAuthErrorLike | null;
}

/**
 * The auth surface this module uses. Tests pass a fake of this shape, so the
 * unit suite never needs the live Supabase service; `SupabaseClient` from
 * `@supabase/supabase-js` satisfies it structurally.
 */
export interface AuthClientLike {
  auth: {
    signUp(credentials: {
      email: string;
      password: string;
    }): Promise<ClientAuthResultLike>;
    signInWithPassword(credentials: {
      email: string;
      password: string;
    }): Promise<ClientAuthResultLike>;
    signOut(): Promise<{ error: ClientAuthErrorLike | null }>;
    getSession(): Promise<ClientSessionResultLike>;
  };
}

/** Why an authentication operation failed. */
export type AuthFailureReason =
  | "unconfigured"
  | "invalid-input"
  | "invalid-credentials"
  | "email-not-confirmed"
  | "already-registered"
  | "rate-limited"
  | "rejected"
  | "unexpected";

/**
 * Outcome of signup or login. Success is either a live session or the state
 * where Supabase still needs the address confirmed — a user awaiting
 * confirmation is deliberately **not** reported as signed in.
 */
export type AuthActionResult =
  | { ok: true; status: "signed-in"; userId: string }
  | { ok: true; status: "confirmation-required"; email: string }
  | { ok: false; reason: AuthFailureReason; message: string };

/** Outcome of signing out. */
export type SignOutResult =
  | { ok: true }
  | { ok: false; reason: AuthFailureReason; message: string };

/**
 * Whether this browser has a Supabase session. `unconfigured` (no Supabase
 * project is configured) and `error` (the session could not be read) are
 * distinct from `unauthenticated`, so a broken check never looks like a
 * signed-out user.
 */
export type SessionState =
  | { status: "unconfigured" }
  | { status: "authenticated"; userId: string; email: string | null }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

/** Supabase's default minimum; checked here before calling the provider. */
const MIN_PASSWORD_LENGTH = 6;

const UNCONFIGURED_MESSAGE =
  "Authentication is not available: Supabase is not configured for this environment.";
const UNEXPECTED_MESSAGE = "An unexpected error occurred. Please try again.";
const SESSION_UNREADABLE_MESSAGE =
  "Your session could not be read. Try signing in again.";
const REJECTED_SIGNUP_MESSAGE =
  "Signup was rejected. Check the email address and password and try again.";
const REJECTED_LOGIN_MESSAGE = "Email or password is incorrect.";
const RATE_LIMITED_MESSAGE = "Too many attempts. Wait a moment and try again.";

function resolveClient(client?: AuthClientLike): AuthClientLike | null {
  return client ?? getSupabaseClient();
}

function invalidCredentials(
  email: string,
  password: string,
): { reason: AuthFailureReason; message: string } | null {
  const trimmed = email.trim();
  if (!trimmed.includes("@") || trimmed.length < 3) {
    return { reason: "invalid-input", message: "Enter a valid email address." };
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return {
      reason: "invalid-input",
      message: `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`,
    };
  }
  return null;
}

function normalizeEmail(email: ClientUserLike["email"]): string | null {
  return typeof email === "string" && email.length > 0 ? email : null;
}

/**
 * Map a Supabase auth error to a reason and a fixed message of our own.
 * `error.message` is intentionally never used: provider text is not a stable
 * or safe user-facing contract, and it must not reach a log either.
 */
function classifyAuthError(
  error: ClientAuthErrorLike,
  operation: "signup" | "login",
): { reason: AuthFailureReason; message: string } {
  switch (error.code) {
    case "invalid_credentials":
      return { reason: "invalid-credentials", message: REJECTED_LOGIN_MESSAGE };
    case "email_not_confirmed":
      return {
        reason: "email-not-confirmed",
        message: "Confirm your email address before signing in.",
      };
    case "user_already_exists":
    case "email_exists":
      return {
        reason: "already-registered",
        message: "An account with this email address already exists.",
      };
    case "weak_password":
      return { reason: "rejected", message: "Choose a stronger password." };
    case "over_email_send_rate_limit":
    case "over_request_rate_limit":
      return { reason: "rate-limited", message: RATE_LIMITED_MESSAGE };
    default:
      break;
  }

  if (error.status === 429) {
    return { reason: "rate-limited", message: RATE_LIMITED_MESSAGE };
  }
  if (error.status === 400 || error.status === 401 || error.status === 422) {
    // Supabase answers a wrong password and an unknown account identically, so
    // the login wording is the same for both.
    return operation === "login"
      ? { reason: "invalid-credentials", message: REJECTED_LOGIN_MESSAGE }
      : { reason: "rejected", message: REJECTED_SIGNUP_MESSAGE };
  }
  return { reason: "unexpected", message: UNEXPECTED_MESSAGE };
}

/**
 * Create an account with email and password.
 *
 * When Supabase still requires email confirmation there is no session, so the
 * result is `confirmation-required` — never a pretend sign-in.
 */
export async function signUpWithEmail(
  email: string,
  password: string,
  client?: AuthClientLike,
): Promise<AuthActionResult> {
  const invalid = invalidCredentials(email, password);
  if (invalid !== null) {
    return { ok: false, ...invalid };
  }

  const auth = resolveClient(client);
  if (auth === null) {
    return { ok: false, reason: "unconfigured", message: UNCONFIGURED_MESSAGE };
  }

  try {
    const { data, error } = await auth.auth.signUp({
      email: email.trim(),
      password,
    });

    if (error !== null) {
      return { ok: false, ...classifyAuthError(error, "signup") };
    }
    if (data.session !== null) {
      return { ok: true, status: "signed-in", userId: data.session.user.id };
    }
    if (data.user !== null) {
      // Supabase deliberately answers the same way for "check your inbox" and
      // for an address that already exists, so this state is reported as
      // pending confirmation rather than asserting which one it is.
      return { ok: true, status: "confirmation-required", email: email.trim() };
    }
    return { ok: false, reason: "unexpected", message: UNEXPECTED_MESSAGE };
  } catch {
    return { ok: false, reason: "unexpected", message: UNEXPECTED_MESSAGE };
  }
}

/** Sign in with email and password. A session is required to report success. */
export async function signInWithEmail(
  email: string,
  password: string,
  client?: AuthClientLike,
): Promise<AuthActionResult> {
  const invalid = invalidCredentials(email, password);
  if (invalid !== null) {
    return { ok: false, ...invalid };
  }

  const auth = resolveClient(client);
  if (auth === null) {
    return { ok: false, reason: "unconfigured", message: UNCONFIGURED_MESSAGE };
  }

  try {
    const { data, error } = await auth.auth.signInWithPassword({
      email: email.trim(),
      password,
    });

    if (error !== null) {
      return { ok: false, ...classifyAuthError(error, "login") };
    }
    if (data.session === null) {
      // No session means no authenticated user, whatever else the answer said.
      return { ok: false, reason: "unexpected", message: UNEXPECTED_MESSAGE };
    }
    return { ok: true, status: "signed-in", userId: data.session.user.id };
  } catch {
    return { ok: false, reason: "unexpected", message: UNEXPECTED_MESSAGE };
  }
}

/** End the current session and clear the session Supabase stores. */
export async function signOut(client?: AuthClientLike): Promise<SignOutResult> {
  const auth = resolveClient(client);
  if (auth === null) {
    return { ok: false, reason: "unconfigured", message: UNCONFIGURED_MESSAGE };
  }

  try {
    const { error } = await auth.auth.signOut();
    if (error !== null) {
      return { ok: false, ...classifyAuthError(error, "login") };
    }
    return { ok: true };
  } catch {
    return { ok: false, reason: "unexpected", message: UNEXPECTED_MESSAGE };
  }
}

/** Read the current session from the storage Supabase manages. */
export async function getCurrentSession(
  client?: AuthClientLike,
): Promise<SessionState> {
  const auth = resolveClient(client);
  if (auth === null) {
    return { status: "unconfigured" };
  }

  try {
    const { data, error } = await auth.auth.getSession();
    if (error !== null) {
      return { status: "error", message: SESSION_UNREADABLE_MESSAGE };
    }
    if (data.session === null) {
      return { status: "unauthenticated" };
    }
    return {
      status: "authenticated",
      userId: data.session.user.id,
      email: normalizeEmail(data.session.user.email),
    };
  } catch {
    return { status: "error", message: SESSION_UNREADABLE_MESSAGE };
  }
}

/**
 * Return the session's access token for an authenticated API call, or `null`.
 *
 * The token is handed straight to the caller for the request being made — this
 * module never stores, caches, logs, or renders it, and no component reads it
 * directly. `null` means "no usable session" (unconfigured, signed out, or
 * unreadable), which callers must treat the same way as an unauthenticated
 * request.
 */
export async function getAccessToken(
  client?: AuthClientLike,
): Promise<string | null> {
  const auth = resolveClient(client);
  if (auth === null) {
    return null;
  }

  try {
    const { data, error } = await auth.auth.getSession();
    if (error !== null || data.session === null) {
      return null;
    }
    const token = data.session.access_token;
    return typeof token === "string" && token.length > 0 ? token : null;
  } catch {
    return null;
  }
}


