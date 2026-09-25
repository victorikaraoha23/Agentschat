/**
 * Health-check request against the FastAPI backend — the only API call the
 * application makes today (Task 1.5 integration smoke test).
 *
 * Colocated with the page that uses it (see the conventions in README.md);
 * move to `lib/` when a second caller appears.
 */

/**
 * Where the browser finds the FastAPI backend. It is public by necessity —
 * `NEXT_PUBLIC_*` values are embedded in the client bundle — so this must
 * never hold a secret (root AGENTS.md §16).
 */
export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

/** Expected body of GET /health. */
export interface HealthResponse {
  status: string;
}

/**
 * Result of a health check. The function never throws, so callers can render
 * every variant without a crash boundary (Task 1.5, Step 5).
 */
export type HealthCheckResult =
  | { ok: true; status: string }
  | { ok: false; reason: "network"; message: string }
  | { ok: false; reason: "http"; message: string; statusCode: number }
  | { ok: false; reason: "invalid-response"; message: string }
  | { ok: false; reason: "unexpected"; message: string };

/**
 * The subset of `fetch` this module uses — the seam tests inject, so tests
 * never touch the network.
 */
type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

const defaultFetch: FetchLike = (url, init) => fetch(url, init);

const HEALTH_CHECK_TIMEOUT_MS = 5_000;

/** Shown when something outside the classified cases fails; never carries raw error text. */
const UNEXPECTED_FAILURE_MESSAGE =
  "An unexpected error occurred while checking the API.";

/** Request GET /health and classify the outcome; never throws. */
export async function checkApiHealth(
  fetchImpl: FetchLike = defaultFetch,
): Promise<HealthCheckResult> {
  const url = `${API_BASE_URL.replace(/\/+$/, "")}/health`;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetchImpl(url, { signal: controller.signal });
    } catch (error: unknown) {
      return {
        ok: false,
        reason: "network",
        message: error instanceof Error ? error.message : "Request failed.",
      };
    }

    if (controller.signal.aborted) {
      return {
        ok: false,
        reason: "network",
        message: "API health check timed out.",
      };
    }

    if (!response.ok) {
      return {
        ok: false,
        reason: "http",
        message: `API responded with HTTP ${response.status}.`,
        statusCode: response.status,
      };
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      if (controller.signal.aborted) {
        return {
          ok: false,
          reason: "network",
          message: "API health check timed out.",
        };
      }
      return {
        ok: false,
        reason: "invalid-response",
        message: "API response was not valid JSON.",
      };
    }

    if (controller.signal.aborted) {
      return {
        ok: false,
        reason: "network",
        message: "API health check timed out.",
      };
    }

    if (
      typeof body !== "object" ||
      body === null ||
      !("status" in body) ||
      typeof body.status !== "string"
    ) {
      return {
        ok: false,
        reason: "invalid-response",
        message: "API response did not contain a status string.",
      };
    }

    return { ok: true, status: body.status };
  } catch {
    // Anything not classified above — for example a response object that misbehaves —
    // is an unexpected failure. Report it safely rather than letting it reach the page.
    return { ok: false, reason: "unexpected", message: UNEXPECTED_FAILURE_MESSAGE };
  } finally {
    clearTimeout(deadline);
  }
}
