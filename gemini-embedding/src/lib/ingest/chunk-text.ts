import type { PendingChunk } from "../types";
import { estimateTokens } from "../media";

/**
 * gemini-embedding-2 accepts 8,192 text tokens per request. We window well
 * under that so the `title: ... | text: ...` prefix always fits and so each
 * vector stays topically tight.
 */
const TARGET_TOKENS = 1200;
const OVERLAP_RATIO = 0.15;
const TARGET_CHARS = TARGET_TOKENS * 4;
const OVERLAP_CHARS = Math.floor(TARGET_CHARS * OVERLAP_RATIO);

/** Prefer to break on paragraph, then sentence, then whitespace boundaries. */
function findBreak(text: string, from: number, to: number) {
  const window = text.slice(from, to);
  for (const pattern of [/\n\s*\n/g, /(?<=[.!?])\s+/g, /\s+/g]) {
    let last = -1;
    for (const match of window.matchAll(pattern)) {
      // Only accept breaks in the last third, so chunks stay near target size.
      if (match.index > window.length * 0.6) last = match.index + match[0].length;
    }
    if (last > 0) return from + last;
  }
  return to;
}

export function chunkText(text: string): PendingChunk[] {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  if (!normalized) return [];

  const chunks: PendingChunk[] = [];
  let cursor = 0;

  while (cursor < normalized.length) {
    const hardEnd = Math.min(cursor + TARGET_CHARS, normalized.length);
    const end = hardEnd === normalized.length ? hardEnd : findBreak(normalized, cursor, hardEnd);
    const slice = normalized.slice(cursor, end).trim();

    if (slice) {
      chunks.push({
        modality: "text",
        content: slice,
        meta: { char_start: cursor, char_end: end },
      });
    }

    if (end >= normalized.length) break;
    cursor = Math.max(end - OVERLAP_CHARS, cursor + 1);
  }

  return chunks;
}

export { estimateTokens };
