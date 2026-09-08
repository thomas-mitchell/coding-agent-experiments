import type { MediaKind } from "./media";

export type { MediaKind };

export type DocumentStatus = "pending" | "processing" | "ready" | "error";

export type DocumentRow = {
  id: string;
  rel_path: string;
  filename: string;
  mime_type: string;
  media_kind: MediaKind;
  size_bytes: number;
  sha256: string;
  status: DocumentStatus;
  error: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
};

export type ChunkMeta = {
  page_start?: number;
  page_end?: number;
  start_sec?: number;
  end_sec?: number;
  char_start?: number;
  char_end?: number;
};

export type MatchedChunk = {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  modality: string;
  content: string;
  meta: ChunkMeta;
  similarity: number;
  filename: string;
  rel_path: string;
  mime_type: string;
  media_kind: MediaKind;
};

/** One unit of work produced by a splitter, before embedding. */
export type PendingChunk = {
  modality: MediaKind;
  /** Displayable text: the chunk itself for text, a description for media. */
  content: string;
  meta: ChunkMeta;
  /** Present for media chunks; absent for text chunks. */
  media?: { bytes: Buffer; mimeType: string };
};

export type IngestEvent =
  | { type: "scan"; total: number; pending: number }
  | { type: "document:start"; relPath: string; kind: MediaKind }
  | { type: "document:chunks"; relPath: string; chunks: number }
  | { type: "document:progress"; relPath: string; done: number; total: number }
  | { type: "document:done"; relPath: string; chunks: number }
  | { type: "document:error"; relPath: string; message: string }
  | { type: "document:skip"; relPath: string; reason: string }
  | { type: "complete"; embedded: number; skipped: number; failed: number };
