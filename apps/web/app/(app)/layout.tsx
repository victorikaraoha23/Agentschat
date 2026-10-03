import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "AgentsChat",
};

/** Pass app routes through without extra chrome; AppShell owns the session UI. */
export default function AppLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
