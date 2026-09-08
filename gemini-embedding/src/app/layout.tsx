import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Multimodal RAG - Gemini Embedding 2",
  description:
    "Index text, images, audio, video and PDFs with gemini-embedding-2, retrieve from Supabase pgvector, reason with an OpenAI Codex model.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
