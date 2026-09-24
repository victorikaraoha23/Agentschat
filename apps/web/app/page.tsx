"use client";

import { useEffect, useState } from "react";

import { checkApiHealth, type HealthCheckResult } from "./health-api";

export default function Home() {
  const [health, setHealth] = useState<HealthCheckResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    void checkApiHealth().then((result) => {
      if (!cancelled) {
        setHealth(result);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main>
      <h1>AgentsChat</h1>
      <p>
        A hosted, beginner-friendly AI-agent workspace. Describe what you need in plain language and the
        hosted system handles agent execution, tools, files, and memory.
      </p>
      <p className="muted">
        This page is the foundation of the web application and exists to show that the Next.js app renders.
        Chat, accounts, and agent execution are not implemented yet.
      </p>
      <section aria-label="Integration status" aria-live="polite">
        <p className="status-line">
          Frontend: <strong>running</strong>
        </p>
        <p className="status-line">
          Backend health check:{" "}
          {health === null ? (
            <span className="status-pending">checking…</span>
          ) : health.ok ? (
            <span className="status-ok">succeeded ({health.status})</span>
          ) : (
            <span className="status-error">failed — {health.message}</span>
          )}
        </p>
      </section>
    </main>
  );
}
