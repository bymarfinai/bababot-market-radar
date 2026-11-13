import type { Metadata } from "next";
import "./globals.css";
import "./chart.css";
import "./journal.css";
import "./live.css";

export const metadata: Metadata = {
  title: "BabaBot vNext | LIVE & RESEARCH",
  description: "Separated LIVE monitoring shell and independent VPS2 PAPER research — read only.",
  robots: { index: false, follow: false }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
