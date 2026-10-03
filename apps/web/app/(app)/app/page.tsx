import { AppShell } from "@/components/app-shell";

/** Render the app entry point, delegating session gating to AppShell. */
export default function AppPage() {
  return (
    <main>
      <h1>App</h1>
      <AppShell />
    </main>
  );
}
