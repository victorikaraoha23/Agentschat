import assert from "node:assert/strict";
import { test } from "node:test";

import { checkApiHealth } from "./health-api.ts";

const healthyResponse = () =>
  new Response(JSON.stringify({ status: "healthy" }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

test("requests <base>/health and returns the healthy status", async () => {
  let requestedUrl: string | undefined;
  const result = await checkApiHealth(async (url) => {
    requestedUrl = url;
    return healthyResponse();
  });

  assert.match(requestedUrl ?? "", /\/health$/);
  assert.deepEqual(result, { ok: true, status: "healthy" });
});

test("returns an http failure for an unsuccessful response", async () => {
  const result = await checkApiHealth(
    async () => new Response("boom", { status: 500 }),
  );

  assert.deepEqual(result, {
    ok: false,
    reason: "http",
    statusCode: 500,
    message: "API responded with HTTP 500.",
  });
});

test("returns a network failure when the request rejects", async () => {
  const result = await checkApiHealth(async () => {
    throw new TypeError("fetch failed");
  });

  assert.deepEqual(result, {
    ok: false,
    reason: "network",
    message: "fetch failed",
  });
});

test("keeps the deadline active while parsing the response body", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => t.mock.timers.reset());

  let signal: AbortSignal | undefined;
  const response = healthyResponse();
  response.json = () =>
    new Promise((resolve) => {
      const requestSignal = signal;
      if (!requestSignal) {
        throw new Error("Expected an abort signal.");
      }
      requestSignal.addEventListener("abort", () => resolve({ status: "healthy" }), {
        once: true,
      });
    });

  const resultPromise = checkApiHealth(async (_, init) => {
    signal = init?.signal ?? undefined;
    return response;
  });

  await new Promise<void>((resolve) => queueMicrotask(resolve));
  t.mock.timers.tick(5_000);

  assert.deepEqual(await resultPromise, {
    ok: false,
    reason: "network",
    message: "API health check timed out.",
  });
});

test("clears the deadline after parsing the response body", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  t.after(() => t.mock.timers.reset());

  let signal: AbortSignal | undefined;
  const result = await checkApiHealth(async (_, init) => {
    signal = init?.signal ?? undefined;
    return healthyResponse();
  });

  t.mock.timers.tick(5_000);

  assert.deepEqual(result, { ok: true, status: "healthy" });
  assert.equal(signal?.aborted, false);
});

test("rejects a 200 response whose body is not valid JSON", async () => {
  const result = await checkApiHealth(
    async () => new Response("<html>oops</html>", { status: 200 }),
  );

  assert.deepEqual(result, {
    ok: false,
    reason: "invalid-response",
    message: "API response was not valid JSON.",
  });
});

test("rejects valid JSON that does not carry a status string", async () => {
  const wrongShape = await checkApiHealth(
    async () =>
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  );
  assert.deepEqual(wrongShape, {
    ok: false,
    reason: "invalid-response",
    message: "API response did not contain a status string.",
  });

  const notAnObject = await checkApiHealth(
    async () =>
      new Response(JSON.stringify("healthy"), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  );
  assert.equal(notAnObject.ok, false);
});
