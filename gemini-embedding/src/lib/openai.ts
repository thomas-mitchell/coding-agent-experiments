import "server-only";
import OpenAI from "openai";
import { env } from "./env";
import type { MatchedChunk } from "./types";

let cached: OpenAI | null = null;

function client() {
  if (!cached) cached = new OpenAI({ apiKey: env().OPENAI_API_KEY });
  return cached;
}

const SYSTEM_INSTRUCTIONS = `You answer questions using ONLY the numbered context passages provided.

The passages come from a multimodal index, so a passage may describe an image, a
video segment, an audio segment, or a page range of a PDF rather than plain text.
For media passages you are given the source filename and position, not the media
itself - describe what the passage supports, and do not invent visual or audio
detail you cannot see.

Rules:
- Cite every claim with the bracketed passage number it came from, e.g. [2].
- If the passages do not contain the answer, say so plainly and state what is missing.
- Do not use outside knowledge to fill gaps in the passages.
- Be concise and concrete.`;

function renderContext(chunks: MatchedChunk[]) {
  return chunks
    .map((chunk, index) => {
      const meta: string[] = [`source: ${chunk.rel_path}`, `type: ${chunk.media_kind}`];
      const m = chunk.meta ?? {};
      if (m.page_start != null) meta.push(`pages ${m.page_start}-${m.page_end}`);
      if (m.start_sec != null) meta.push(`time ${fmt(m.start_sec)}-${fmt(m.end_sec ?? 0)}`);
      meta.push(`similarity: ${chunk.similarity.toFixed(3)}`);
      const body = chunk.content?.trim()
        ? chunk.content.trim()
        : `(no extractable text - this is a ${chunk.media_kind} segment matched by its embedding)`;
      return `[${index + 1}] (${meta.join(", ")})\n${body}`;
    })
    .join("\n\n");
}

function fmt(seconds: number) {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export async function reason(question: string, chunks: MatchedChunk[], effort?: string) {
  const { OPENAI_MODEL, OPENAI_REASONING_EFFORT } = env();

  if (chunks.length === 0) {
    return {
      answer:
        "Nothing in the index passed the similarity threshold for this question. " +
        "Try lowering the minimum similarity, widening the media-kind filter, or embedding more documents.",
      model: OPENAI_MODEL,
    };
  }

  // Codex-line models are available on the Responses API only.
  const response = await client().responses.create({
    model: OPENAI_MODEL,
    instructions: SYSTEM_INSTRUCTIONS,
    reasoning: { effort: (effort ?? OPENAI_REASONING_EFFORT) as "low" | "medium" | "high" },
    input: `Context passages:\n\n${renderContext(chunks)}\n\n---\n\nQuestion: ${question}`,
  });

  return { answer: response.output_text ?? "", model: OPENAI_MODEL };
}
