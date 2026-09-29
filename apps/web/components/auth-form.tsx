"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import styles from "./auth-form.module.css";

/** What the form shows after a submit attempt. */
export interface AuthFormOutcome {
  ok: boolean;
  message: string;
}

interface AuthFormProps {
  /** Rendered as the page heading. */
  title: string;
  description: string;
  submitLabel: string;
  pendingLabel: string;
  passwordAutoComplete: "new-password" | "current-password";
  /** Runs the authentication operation and returns the state to display. */
  onSubmit: (email: string, password: string) => Promise<AuthFormOutcome>;
  /** Navigation to the other authentication page. */
  footer: ReactNode;
}

/**
 * The email/password form shared by `/signup` and `/login`.
 *
 * It owns only presentation and submission state; every authentication
 * decision lives in `lib/auth.ts`, which is why the form receives the outcome
 * instead of calling Supabase itself.
 */
export function AuthForm({
  title,
  description,
  submitLabel,
  pendingLabel,
  passwordAutoComplete,
  onSubmit,
  footer,
}: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [outcome, setOutcome] = useState<AuthFormOutcome | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setOutcome(null);
    try {
      setOutcome(await onSubmit(email, password));
    } catch {
      // The boundary never throws; this only guards against a future bug so the
      // form cannot appear to have submitted successfully.
      setOutcome({
        ok: false,
        message: "An unexpected error occurred. Please try again.",
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <h1>{title}</h1>
      <p className="muted">{description}</p>
      <form className={styles.form} onSubmit={handleSubmit} noValidate>
        <label className={styles.field} htmlFor="email">
          Email
          <input
            className={styles.input}
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>
        <label className={styles.field} htmlFor="password">
          Password
          <input
            className={styles.input}
            id="password"
            name="password"
            type="password"
            autoComplete={passwordAutoComplete}
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <span className={styles.hint}>At least 6 characters.</span>
        </label>
        <button type="submit" disabled={pending} aria-busy={pending}>
          {pending ? pendingLabel : submitLabel}
        </button>
      </form>
      {outcome !== null && (
        <p
          className={`${styles.message} ${outcome.ok ? styles.ok : styles.error}`}
          role={outcome.ok ? "status" : "alert"}
          aria-live="polite"
        >
          {outcome.message}
        </p>
      )}
      <p className={styles.footer}>{footer}</p>
    </>
  );
}
