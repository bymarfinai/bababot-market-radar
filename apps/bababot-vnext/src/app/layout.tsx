import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BabaBot vNext | STRONG LONG",
  description: "Independent PAPER strategy analytics — read only.",
  robots: { index: false, follow: false }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
