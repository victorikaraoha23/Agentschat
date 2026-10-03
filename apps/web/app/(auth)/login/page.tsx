"use client";

import Link from "next/link";

import { AuthForm, type AuthFormOutcome } from "@/components/auth-form";
import { signInWithEmail, type AuthActionResult } from "@/lib/auth";

function describeSignIn(result: AuthActionResult): AuthFormOutcome {
  if (!result.ok) {
    return { ok: false, message: result.message };
  }
  if (result.status === "confirmation-required") {
    // Sign-in cannot require confirmation, but never report a sign-in we did not get.
    return { ok: false, message: "Confirm your email address before signing in." };
  }
  return {
    ok: true,
    message: "Signed in. Open the home page to see your session.",
  };
}

export default function LoginPage() {
  return (
    <main>
      <AuthForm
        title="Sign in"
        description="Sign in with the email address and password you signed up with."
        submitLabel="Sign in"
        pendingLabel="Signing in…"
        passwordAutoComplete="current-password"
        onSubmit={async (email, password) =>
          describeSignIn(await signInWithEmail(email, password))
        }
        footer={
          <>
            No account yet? <Link href="/signup">Create one</Link>.{" "}
            <Link href="/">Back to the home page</Link>.
          </>
        }
      />
    </main>
  );
}
