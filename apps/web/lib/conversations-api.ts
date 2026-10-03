/**
 * Conversation requests against the AgentsChat API (Tasks 5.2–5.3).
 *
 * The browser asks the backend to create one conversation for the signed-in
 * user, to list the conversations that user owns, and to read one of them by id.
 * Ownership comes from the session's access token, which the backend verifies —
 * this module never sends a user id, so there is nothing to forge and no user id
 * appears in a URL either.
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

/** Why a conversation request failed. */
export type ConversationFailureReason =
  | "unauthenticated"
  | "invalid-input"
  | "not-found"
  | "network"
  | "http"
  | "invalid-response"
  | "unexpected";

/**
 * The outcome of a request that answers with one conversation.
 *
 * `not-found` is reachable only by reading: a conversation the user does not
 * own is reported exactly like one that does not exist, because the API answers
 * both the same way.
 */
export type ConversationResult =
  | { ok: true; conversation: Conversation }
  | { ok: false; reason: ConversationFailureReason; message: string; statusCode?: number };

/** The outcome of a request that answers with the user's conversations. */
export type ConversationListResult =
  | { ok: true; conversations: Conversation[] }
  | { ok: false; reason: ConversationFailureReason; message: string; statusCode?: number };

const CREATE_UNREADABLE_SESSION_MESSAGE =
  "Your conversation could not be created: sign in again.";
const CREATE_REJECTED_MESSAGE =
  "Your conversation could not be created: your session is not valid.";
const INVALID_TITLE_MESSAGE = "Give the conversation a title of 200 characters or fewer.";
const CREATE_TIMEOUT_MESSAGE = "Creating your conversation timed out.";
const CREATE_UNEXPECTED_MESSAGE = "An unexpected error occurred while creating your conversation.";

const LIST_UNREADABLE_SESSION_MESSAGE =
  "Your conversations could not be loaded: sign in again.";
const LIST_REJECTED_MESSAGE =
  "Your conversations could not be loaded: your session is not valid.";
const LIST_TIMEOUT_MESSAGE = "Loading your conversations timed out.";
const LIST_UNEXPECTED_MESSAGE = "An unexpected error occurred while loading your conversations.";
const LIST_INVALID_RESPONSE_MESSAGE = "The API response did not contain a conversation list.";

const READ_UNREADABLE_SESSION_MESSAGE = "Your conversation could not be loaded: sign in again.";
const READ_REJECTED_MESSAGE =
  "Your conversation could not be loaded: your session is not valid.";
const READ_TIMEOUT_MESSAGE = "Loading your conversation timed out.";
const READ_UNEXPECTED_MESSAGE = "An unexpected error occurred while loading your conversation.";
const READ_INVALID_ID_MESSAGE = "That conversation id is not valid.";
const NOT_FOUND_MESSAGE = "That conversation could not be found.";

// Failures every request in this module shares, so they read the same way
// wherever they surface.
const REQUEST_FAILED_MESSAGE = "Request failed.";
const INVALID_JSON_MESSAGE = "The API response was not valid JSON.";
const NO_CONVERSATION_MESSAGE = "The API response did not contain a conversation.";

const REQUEST_TIMEOUT_MS = 5_000;

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
): Promise<ConversationResult> {
  const token =
    options.accessToken !== undefined ? options.accessToken : await getAccessToken();
  if (token === null || token === "") {
    return {
      ok: false,
      reason: "unauthenticated",
      message: CREATE_UNREADABLE_SESSION_MESSAGE,
    };
  }

  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const url = `${API_BASE_URL.replace(/\/+$/, "")}/conversations`;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

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
        ? { ok: false, reason: "network", message: CREATE_TIMEOUT_MESSAGE }
        : { ok: false, reason: "network", message: REQUEST_FAILED_MESSAGE };
    }

    if (response.status === 401 || response.status === 403) {
      return {
        ok: false,
        reason: "unauthenticated",
        message: CREATE_REJECTED_MESSAGE,
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
        return { ok: false, reason: "network", message: CREATE_TIMEOUT_MESSAGE };
      }
      return {
        ok: false,
        reason: "invalid-response",
        message: INVALID_JSON_MESSAGE,
      };
    }

    if (!isConversationPayload(body)) {
      return {
        ok: false,
        reason: "invalid-response",
        message: NO_CONVERSATION_MESSAGE,
      };
    }

    return { ok: true, conversation: toConversation(body) };
  } catch {
    // Anything unclassified stays a safe, fixed message rather than raw text.
    return { ok: false, reason: "unexpected", message: CREATE_UNEXPECTED_MESSAGE };
  } finally {
    clearTimeout(deadline);
  }
}

/** The list as the API returns it: an object wrapping `items`. */
interface ConversationListPayload {
  items: ConversationPayload[];
}

/** Whether JSON is the contracted shape of `GET /conversations`. */
function isConversationListPayload(body: unknown): body is ConversationListPayload {
  if (typeof body !== "object" || body === null || !("items" in body)) {
    return false;
  }
  if (!Array.isArray(body.items)) {
    return false;
  }
  return body.items.every(isConversationPayload);
}

/** Request options; every field exists so tests never touch the network. */
export interface ListConversationsRequestOptions {
  /** Session access token. Omit to read it from the current session. */
  accessToken?: string | null;
  fetchImpl?: FetchLike;
}

/**
 * Request `GET /conversations` with the session's access token and classify
 * the outcome.
 *
 * Only the bearer token is sent — never a user id — so ownership is decided by
 * the server from the token it verifies. An account with no conversations is a
 * success with an empty array, and the API's ordering (most recently updated
 * first) is preserved as received. The function never throws.
 */
export async function listConversations(
  options: ListConversationsRequestOptions = {},
): Promise<ConversationListResult> {
  const token =
    options.accessToken !== undefined ? options.accessToken : await getAccessToken();
  if (token === null || token === "") {
    return {
      ok: false,
      reason: "unauthenticated",
      message: LIST_UNREADABLE_SESSION_MESSAGE,
    };
  }

  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const url = `${API_BASE_URL.replace(/\/+$/, "")}/conversations`;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetchImpl(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
    } catch {
      return controller.signal.aborted
        ? { ok: false, reason: "network", message: LIST_TIMEOUT_MESSAGE }
        : { ok: false, reason: "network", message: REQUEST_FAILED_MESSAGE };
    }

    if (response.status === 401 || response.status === 403) {
      return {
        ok: false,
        reason: "unauthenticated",
        message: LIST_REJECTED_MESSAGE,
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
        return { ok: false, reason: "network", message: LIST_TIMEOUT_MESSAGE };
      }
      return { ok: false, reason: "invalid-response", message: INVALID_JSON_MESSAGE };
    }

    if (!isConversationListPayload(body)) {
      return {
        ok: false,
        reason: "invalid-response",
        message: LIST_INVALID_RESPONSE_MESSAGE,
      };
    }

    return { ok: true, conversations: body.items.map(toConversation) };
  } catch {
    return { ok: false, reason: "unexpected", message: LIST_UNEXPECTED_MESSAGE };
  } finally {
    clearTimeout(deadline);
  }
}

/** Request options; `conversationId` is an id this API returned earlier. */
export interface GetConversationRequestOptions {
  conversationId: string;
  /** Session access token. Omit to read it from the current session. */
  accessToken?: string | null;
  fetchImpl?: FetchLike;
}

/**
 * Request `GET /conversations/{conversation_id}` with the session's access
 * token and classify the outcome.
 *
 * The id travels in the URL path while ownership is decided server-side from
 * the verified token. A conversation belonging to someone else answers exactly
 * like one that does not exist (`not-found`), because the API deliberately
 * reports both the same way — this module must not tell them apart. The
 * function never throws.
 */
export async function getConversation(
  options: GetConversationRequestOptions,
): Promise<ConversationResult> {
  const token =
    options.accessToken !== undefined ? options.accessToken : await getAccessToken();
  if (token === null || token === "") {
    return {
      ok: false,
      reason: "unauthenticated",
      message: READ_UNREADABLE_SESSION_MESSAGE,
    };
  }

  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const base = API_BASE_URL.replace(/\/+$/, "");
  const url = `${base}/conversations/${encodeURIComponent(options.conversationId)}`;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetchImpl(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
    } catch {
      return controller.signal.aborted
        ? { ok: false, reason: "network", message: READ_TIMEOUT_MESSAGE }
        : { ok: false, reason: "network", message: REQUEST_FAILED_MESSAGE };
    }

    if (response.status === 401 || response.status === 403) {
      return {
        ok: false,
        reason: "unauthenticated",
        message: READ_REJECTED_MESSAGE,
        statusCode: response.status,
      };
    }
    if (response.status === 404) {
      return { ok: false, reason: "not-found", message: NOT_FOUND_MESSAGE, statusCode: 404 };
    }
    if (response.status === 422) {
      return {
        ok: false,
        reason: "invalid-input",
        message: READ_INVALID_ID_MESSAGE,
        statusCode: 422,
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
        return { ok: false, reason: "network", message: READ_TIMEOUT_MESSAGE };
      }
      return { ok: false, reason: "invalid-response", message: INVALID_JSON_MESSAGE };
    }

    if (!isConversationPayload(body)) {
      return { ok: false, reason: "invalid-response", message: NO_CONVERSATION_MESSAGE };
    }

    return { ok: true, conversation: toConversation(body) };
  } catch {
    return { ok: false, reason: "unexpected", message: READ_UNEXPECTED_MESSAGE };
  } finally {
    clearTimeout(deadline);
  }
}


