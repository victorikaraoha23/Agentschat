import { getAccessToken } from "./auth.ts";
import { API_BASE_URL } from "./api-base-url.ts";
interface MessagePayload {
  id: string;
  conversation_id: string;
  user_id: string;
  role: string;
  content: string;
  created_at: string;
}
export interface Message {
  id: string;
  conversationId: string;
  userId: string;
  role: string;
  content: string;
  createdAt: string;
}
export type MessageFailureReason = "unauthenticated" | "invalid-input" | "not-found" | "network" | "http" | "invalid-response" | "unexpected";
export type MessageResult = { ok: true; message: Message } | { ok: false; reason: MessageFailureReason; message: string; statusCode?: number };
export const MESSAGE_CONTENT_MAX_LENGTH = 4000;
export const MESSAGE_TOO_LONG_MESSAGE = "Keep your message to 4000 characters or fewer.";
export function messageContentProblem(content: string): string | null {
  if (content.trim() === "") {
    return "Type a message first.";
  }
  return content.length > MESSAGE_CONTENT_MAX_LENGTH ? MESSAGE_TOO_LONG_MESSAGE : null;
}

const SEND_UNREADABLE_SESSION_MESSAGE = "Your message could not be sent: sign in again.";
const SEND_REJECTED_MESSAGE = "Your message could not be sent: your session is not valid.";
const SEND_TIMEOUT_MESSAGE = "Sending your message timed out.";
const NO_MESSAGE_MESSAGE = "The API response did not contain a message.";
const REQUEST_TIMEOUT_MS = 5_000;
type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
const defaultFetch: FetchLike = (url, init) => fetch(url, init);
export interface CreateMessageRequestOptions {
  conversationId: string;
  content: string;
  accessToken?: string | null;
  fetchImpl?: FetchLike;
}
function isMessagePayload(body: unknown): body is MessagePayload {
  if (typeof body !== "object" || body === null) {
    return false;
  }
  const r = body as Record<string, unknown>;
  return (
    typeof r.id === "string" &&
    typeof r.conversation_id === "string" &&
    typeof r.user_id === "string" &&
    typeof r.role === "string" &&
    typeof r.content === "string" &&
    typeof r.created_at === "string"
  );
}
function toMessage(payload: MessagePayload): Message {
  return {
    id: payload.id,
    conversationId: payload.conversation_id,
    userId: payload.user_id,
    role: payload.role,
    content: payload.content,
    createdAt: payload.created_at,
  };
}
export async function createMessage(options: CreateMessageRequestOptions): Promise<MessageResult> {
  const token = options.accessToken !== undefined ? options.accessToken : await getAccessToken();
  if (token === null || token === "") {
    return { ok: false, reason: "unauthenticated", message: SEND_UNREADABLE_SESSION_MESSAGE };
  }
  const fetchImpl = options.fetchImpl ?? defaultFetch;
  const base = API_BASE_URL.replace(/\/+$/, "");
  const url = base + "/conversations/" + encodeURIComponent(options.conversationId) + "/messages";
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    let response: Response;
    try {
      response = await fetchImpl(url, {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({ content: options.content }),
        signal: controller.signal,
      });
    } catch {
      return controller.signal.aborted
        ? { ok: false, reason: "network", message: SEND_TIMEOUT_MESSAGE }
        : { ok: false, reason: "network", message: "Request failed." };
    }
    if (response.status === 401 || response.status === 403) {
      return { ok: false, reason: "unauthenticated", message: SEND_REJECTED_MESSAGE, statusCode: response.status };
    }
    if (response.status === 404) {
      return { ok: false, reason: "not-found", message: "That conversation could not be found.", statusCode: 404 };
    }
    if (response.status === 422) {
      return { ok: false, reason: "invalid-input", message: "Your message could not be sent: check its content.", statusCode: 422 };
    }
    if (!response.ok) {
      return { ok: false, reason: "http", message: "The API responded with HTTP " + response.status + ".", statusCode: response.status };
    }
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      if (controller.signal.aborted) {
        return { ok: false, reason: "network", message: SEND_TIMEOUT_MESSAGE };
      }
      return { ok: false, reason: "invalid-response", message: "The API response was not valid JSON." };
    }
    if (!isMessagePayload(body)) {
      return { ok: false, reason: "invalid-response", message: NO_MESSAGE_MESSAGE };
    }
    return { ok: true, message: toMessage(body) };
  } catch {
    return { ok: false, reason: "unexpected", message: "An unexpected error occurred while sending your message." };
  } finally {
    clearTimeout(deadline);
  }
}
