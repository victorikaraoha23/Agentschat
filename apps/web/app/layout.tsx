import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AgentsChat",
  description: "A hosted, beginner-friendly AI-agent workspace.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
