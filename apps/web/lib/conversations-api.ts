/**
 * Conversation-creation request against the AgentsChat API (Task 5.2).
 *
 * The browser asks the backend to create one conversation for the signed-in
 * user. Ownership comes from the session's access token, which the backend
 * verifies — this module never sends a user id, so there is nothing to forge.
 *
 * Like the other API modules, nothing here throws: every failure is a typed
 * result carrying a fixed message of our own.
 */

import { getAccessToken } from "./auth.ts";
import { API_BASE_URL } from "./api-base-url.ts";

/** The conversation as the API returns it (snake_case JSON). */
interface ConversationPayload {
  id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

/** The conversation as this application uses it. */
export interface Conversation {
  id: string;
  userId: string;
  title: string | null;
  createdAt: string;
  updatedAt: string;
}

/** Why a creation request failed. */
export type CreateConversationFailureReason =
  | "unauthenticated"
  | "invalid-input"
  | "network"
  | "http"
  | "invalid-response"
  | "unexpected";

export type CreateConversationResult =
  | { ok: true; conversation: Conversation }
  | { ok: false; reason: CreateConversationFailureReason; message: string; statusCode?: number };

const UNREADABLE_SESSION_MESSAGE = "Your conversation could not be created: sign in again.";
const REJECTED_MESSAGE = "Your conversation could not be created: your session is not valid.";
const INVALID_TITLE_MESSAGE = "Give the conversation a title of 200 characters or fewer.";
const UNEXPECTED_MESSAGE = "An unexpected error occurred while creating your conversation.";
const CREATE_TIMEOUT_MS = 5_000;

type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

const defaultFetch: FetchLike = (url, init) => fetch(url, init);

/** Request options; every field exists so tests never touch the network. */
export interface CreateConversationRequestOptions {
  /** Optional title. Omit for an untitled conversation. */
  title?: string;
  /** Session access token. Omit to read it from the current session. */
  accessToken?: string | null;
  fetchImpl?: FetchLike;
}

function toConversation(payload: ConversationPayload): Conversation {
  return {
    id: payload.id,
    userId: payload.user_id,
    title: payload.title,
    createdAt: payload.created_at,
    updatedAt: payload.updated_at,
  };
}

function isConversationPayload(body: unknown): body is ConversationPayload {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  if (!("id" in body) || typeof body.id !== "string") {
    return false;
  }
  if (!("user_id" in body) || typeof body.user_id !== "string") {
    return false;
  }
  if (!("title" in body) || !(typeof body.title === "string" || body.title === null)) {
    return false;
  }
  if (!("created_at" in body) || typeof body.created_at !== "string") {
    return false;
  }
  return "updated_at" in body && typeof body.updated_at === "string";
}

/**
 * Request `POST /conversations` with the session's access token and classify
 * the outcome.
 *
 * Only the bearer token and the optional title are sent — never a user id —
 * because the API derives ownership from the token it verifies. The function
 * never throws.
 */
export async function createConversation(
  options: CreateConversationRequestOptions = {},
): Promise<CreateConversationResult> {
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
  const url = `${API_BASE_URL.replace(/\/+$/, "")}/conversations`;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), CREATE_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetchImpl(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(options.title === undefined ? {} : { title: options.title }),
        signal: controller.signal,
      });
    } catch {
      return controller.signal.aborted
        ? { ok: false, reason: "network", message: "Creating your conversation timed out." }
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
    if (response.status === 422) {
      return {
        ok: false,
        reason: "invalid-input",
        message: INVALID_TITLE_MESSAGE,
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
        return { ok: false, reason: "network", message: "Creating your conversation timed out." };
      }
      return {
        ok: false,
        reason: "invalid-response",
        message: "The API response was not valid JSON.",
      };
    }

    if (!isConversationPayload(body)) {
      return {
        ok: false,
        reason: "invalid-response",
        message: "The API response did not contain a conversation.",
      };
    }

    return { ok: true, conversation: toConversation(body) };
  } catch {
    // Anything unclassified stays a safe, fixed message rather than raw text.
    return { ok: false, reason: "unexpected", message: UNEXPECTED_MESSAGE };
  } finally {
    clearTimeout(deadline);
  }
}

