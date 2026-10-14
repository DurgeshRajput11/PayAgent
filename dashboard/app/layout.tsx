import type { Metadata } from "next";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "PayAgent - Autonomous AI Shopping Dashboard",
  description: "Real-time AI agent audit trail for autonomous commerce powered by Razorpay",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
