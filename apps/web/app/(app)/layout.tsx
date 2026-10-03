import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "AgentsChat",
};

export default function AppLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
