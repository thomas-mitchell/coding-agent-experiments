import path from "node:path";

export type MediaKind = "text" | "image" | "video" | "audio" | "pdf";

/**
 * Per-request limits of gemini-embedding-2. These drive every chunking
 * decision in src/lib/ingest.
 */
export const LIMITS = {
  textTokens: 8192,
  imagesPerRequest: 6,
  videoSeconds: 120,
  audioSeconds: 180,
  pdfPages: 6,
  /** Requests above roughly 20MB are rejected inline; use the Files API instead. */
  inlineMaxBytes: 15 * 1024 * 1024,
} as const;

const EXT_MIME: Record<string, { mime: string; kind: MediaKind }> = {
  // text-ish
  ".txt": { mime: "text/plain", kind: "text" },
  ".md": { mime: "text/markdown", kind: "text" },
  ".markdown": { mime: "text/markdown", kind: "text" },
  ".csv": { mime: "text/csv", kind: "text" },
  ".json": { mime: "application/json", kind: "text" },
  ".jsonl": { mime: "application/json", kind: "text" },
  ".yaml": { mime: "text/yaml", kind: "text" },
  ".yml": { mime: "text/yaml", kind: "text" },
  ".html": { mime: "text/html", kind: "text" },
  ".htm": { mime: "text/html", kind: "text" },
  ".xml": { mime: "text/xml", kind: "text" },
  ".rtf": { mime: "text/plain", kind: "text" },
  ".log": { mime: "text/plain", kind: "text" },
  ".ts": { mime: "text/plain", kind: "text" },
  ".tsx": { mime: "text/plain", kind: "text" },
  ".js": { mime: "text/plain", kind: "text" },
  ".jsx": { mime: "text/plain", kind: "text" },
  ".py": { mime: "text/plain", kind: "text" },
  ".go": { mime: "text/plain", kind: "text" },
  ".rs": { mime: "text/plain", kind: "text" },
  ".java": { mime: "text/plain", kind: "text" },
  ".sql": { mime: "text/plain", kind: "text" },
  ".sh": { mime: "text/plain", kind: "text" },
  // images
  ".png": { mime: "image/png", kind: "image" },
  ".jpg": { mime: "image/jpeg", kind: "image" },
  ".jpeg": { mime: "image/jpeg", kind: "image" },
  ".webp": { mime: "image/webp", kind: "image" },
  ".gif": { mime: "image/gif", kind: "image" },
  // video
  ".mp4": { mime: "video/mp4", kind: "video" },
  ".mov": { mime: "video/quicktime", kind: "video" },
  ".webm": { mime: "video/webm", kind: "video" },
  ".mkv": { mime: "video/x-matroska", kind: "video" },
  ".avi": { mime: "video/x-msvideo", kind: "video" },
  // audio
  ".mp3": { mime: "audio/mpeg", kind: "audio" },
  ".wav": { mime: "audio/wav", kind: "audio" },
  ".m4a": { mime: "audio/mp4", kind: "audio" },
  ".aac": { mime: "audio/aac", kind: "audio" },
  ".ogg": { mime: "audio/ogg", kind: "audio" },
  ".flac": { mime: "audio/flac", kind: "audio" },
  // documents
  ".pdf": { mime: "application/pdf", kind: "pdf" },
};

export function classify(filePath: string) {
  const ext = path.extname(filePath).toLowerCase();
  return EXT_MIME[ext] ?? null;
}

export const SUPPORTED_EXTENSIONS = Object.keys(EXT_MIME);

/** Rough token estimate - good enough for windowing text under the 8,192 cap. */
export function estimateTokens(text: string) {
  return Math.ceil(text.length / 4);
}
