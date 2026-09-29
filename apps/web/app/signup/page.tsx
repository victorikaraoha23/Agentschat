"use client";

import Link from "next/link";

import { AuthForm, type AuthFormOutcome } from "@/components/auth-form";
import { signUpWithEmail, type AuthActionResult } from "@/lib/auth";

function describeSignUp(result: AuthActionResult): AuthFormOutcome {
  if (!result.ok) {
    return { ok: false, message: result.message };
  }
  if (result.status === "confirmation-required") {
    // No session yet: say what happened instead of claiming a sign-in.
    return {
      ok: true,
      message: `Signup submitted for ${result.email}. If the address needs confirming, open the link in your inbox, then sign in.`,
    };
  }
  return {
    ok: true,
    message: "Account created and signed in. Open the home page to see your session.",
  };
}

export default function SignUpPage() {
  return (
    <main>
      <AuthForm
        title="Create your account"
        description="AgentsChat accounts use an email address and password."
        submitLabel="Create account"
        pendingLabel="Creating account…"
        passwordAutoComplete="new-password"
        onSubmit={async (email, password) =>
          describeSignUp(await signUpWithEmail(email, password))
        }
        footer={
          <>
            Already have an account? <Link href="/login">Sign in</Link>.{" "}
            <Link href="/">Back to the home page</Link>.
          </>
        }
      />
    </main>
  );
}
