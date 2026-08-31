import type { Metadata } from "next";
import { Montserrat } from "next/font/google";

import "./globals.css";

// Montserrat is the closest widely available match to the reference's geometric
// sans; the design leans on wide-tracked uppercase, which it handles cleanly.
const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Virtual Try-On",
  description:
    "Upload a person and a garment to generate a composite virtual try-on image.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${montserrat.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
