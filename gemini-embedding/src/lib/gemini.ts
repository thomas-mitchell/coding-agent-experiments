import "server-only";
import { GoogleGenAI } from "@google/genai";
import { env } from "./env";
import { LIMITS } from "./media";

let cached: GoogleGenAI | null = null;

function ai() {
  if (!cached) cached = new GoogleGenAI({ apiKey: env().GEMINI_API_KEY });
  return cached;
}

/**
 * gemini-embedding-2 has no `task_type` parameter (unlike gemini-embedding-001).
 * Task intent is carried by a text prefix instead, and the same convention has
 * to be used on both the indexing and the query side.
 */
export function documentPrefix(title: string, content: string) {
  return `title: ${title} | text: ${content}`;
}

export function queryPrefix(question: string) {
  return `task: question answering | query: ${question}`;
}

export type MediaPayload = {
  bytes: Buffer;
  mimeType: string;
  /** Text placed alongside the media so the vector carries filename context. */
  caption: string;
};

type Part =
  | { text: string }
  | { inlineData: { mimeType: string; data: string } }
  | { fileData: { fileUri: string; mimeType: string } };

async function embedParts(parts: Part[]): Promise<number[]> {
  const { EMBEDDING_MODEL, EMBEDDING_DIMENSIONS } = env();
  const response = await withRetry(() =>
    ai().models.embedContent({
      model: EMBEDDING_MODEL,
      contents: [{ parts }],
      config: { outputDimensionality: EMBEDDING_DIMENSIONS },
    }),
  );

  const values = response.embeddings?.[0]?.values;
  if (!values?.length) throw new Error("Gemini returned an empty embedding");
  if (values.length !== EMBEDDING_DIMENSIONS) {
    throw new Error(
      `Expected ${EMBEDDING_DIMENSIONS}-dim embedding, got ${values.length}. ` +
        `EMBEDDING_DIMENSIONS must match the vector(N) column in the migration.`,
    );
  }
  return values;
}

/** Embed a plain text chunk (already prefixed by the caller). */
export function embedText(text: string) {
  return embedParts([{ text }]);
}

/**
 * Embed one media segment. The caption and the media go in a single `parts`
 * array, which the model aggregates into one vector - so the filename and
 * segment position are folded into the same embedding as the pixels/audio.
 * Segments larger than the inline cap are routed through the Files API.
 */
export async function embedMedia({ bytes, mimeType, caption }: MediaPayload) {
  if (bytes.byteLength <= LIMITS.inlineMaxBytes) {
    return embedParts([
      { text: caption },
      { inlineData: { mimeType, data: bytes.toString("base64") } },
    ]);
  }

  const uploaded = await withRetry(() =>
    ai().files.upload({
      file: new Blob([new Uint8Array(bytes)], { type: mimeType }),
      config: { mimeType },
    }),
  );
  if (!uploaded.uri) throw new Error("Files API upload returned no URI");

  try {
    return await embedParts([
      { text: caption },
      { fileData: { fileUri: uploaded.uri, mimeType } },
    ]);
  } finally {
    if (uploaded.name) {
      await ai()
        .files.delete({ name: uploaded.name })
        .catch(() => {});
    }
  }
}

/** Embed a question. Uses the query-side prefix. */
export function embedQuery(question: string) {
  return embedText(queryPrefix(question));
}

/** Embed an image used as a query, for cross-modal retrieval. */
export function embedQueryImage(bytes: Buffer, mimeType: string) {
  return embedMedia({
    bytes,
    mimeType,
    caption: "task: question answering | query: find content matching this image",
  });
}

const RETRYABLE = /\b(429|500|502|503|504|ECONNRESET|ETIMEDOUT|fetch failed)\b/i;

async function withRetry<T>(fn: () => Promise<T>, attempts = 5): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      const message = error instanceof Error ? error.message : String(error);
      if (!RETRYABLE.test(message) || attempt === attempts - 1) throw error;
      const backoff = Math.min(2 ** attempt * 1000, 16000) + Math.random() * 500;
      await new Promise((resolve) => setTimeout(resolve, backoff));
    }
  }
  throw lastError;
}
