import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { WalletMinimal } from "lucide-react";

import { NavLink } from "@/components/nav-link";
import { ThemeScript } from "@/components/theme-script";
import { ThemeToggle } from "@/components/theme-toggle";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "FinTrack",
  description: "Personal finance tracking and portfolio monitoring.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      data-theme-mode="system"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      // The inline script below rewrites the class and data attribute before
      // React hydrates; this tells React to keep the DOM's version.
      suppressHydrationWarning
    >
      <head>
        <ThemeScript />
      </head>
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
          <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <WalletMinimal className="size-5 text-primary" aria-hidden />
              FinTrack
            </Link>
            <nav aria-label="Main" className="flex items-center gap-1">
              <NavLink href="/">Dashboard</NavLink>
              <NavLink href="/transactions">Transactions</NavLink>
              <NavLink href="/portfolio">Portfolio</NavLink>
            </nav>
            <ThemeToggle />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
          {children}
        </main>
      </body>
    </html>
  );
}
