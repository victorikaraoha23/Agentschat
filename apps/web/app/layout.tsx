import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/next";
import { SpeedInsights } from "@vercel/speed-insights/next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AgentsChat",
  description: "A hosted, beginner-friendly AI-agent workspace.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        {children}
        {/* Vercel Web Analytics and Speed Insights: first-party telemetry that
            only reports from a Vercel deployment (nothing is sent locally). */}
        <Analytics />
        <SpeedInsights />
      </body>
    </html>
  );
}
