import "server-only";
import fs from "node:fs/promises";
import { db } from "../supabase";
import { env } from "../env";
import { documentPrefix, embedMedia, embedText } from "../gemini";
import { resolveInsideRoot } from "../paths";
import type { DocumentRow, IngestEvent, PendingChunk } from "../types";
import { scanDocuments } from "./scan";
import { chunkText } from "./chunk-text";
import { chunkPdf } from "./chunk-pdf";
import { chunkMedia } from "./chunk-media";

/** Turn one file into embeddable units, respecting the model's per-request limits. */
async function split(row: DocumentRow, bytes: Buffer): Promise<PendingChunk[]> {
  switch (row.media_kind) {
    case "text":
      return chunkText(bytes.toString("utf8"));
    case "pdf":
      return chunkPdf(bytes, row.filename);
    case "video":
    case "audio":
      return chunkMedia(bytes, row.mime_type, row.media_kind, row.filename);
    case "image":
      // One image is always one request, so it is always exactly one chunk.
      return [
        {
          modality: "image",
          content: `image "${row.filename}"`,
          meta: {},
          media: { bytes, mimeType: row.mime_type },
        },
      ];
  }
}

function embedOne(row: DocumentRow, chunk: PendingChunk) {
  if (!chunk.media) {
    return embedText(documentPrefix(row.rel_path, chunk.content));
  }
  return embedMedia({
    bytes: chunk.media.bytes,
    mimeType: chunk.media.mimeType,
    caption: documentPrefix(row.rel_path, chunk.content),
  });
}

/** Run `worker` over `items` with a fixed number of workers, preserving order. */
async function pool<T, R>(items: T[], limit: number, worker: (item: T, index: number) => Promise<R>) {
  const results = new Array<R>(items.length);
  let next = 0;
  const runners = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (true) {
      const index = next++;
      if (index >= items.length) return;
      results[index] = await worker(items[index], index);
    }
  });
  await Promise.all(runners);
  return results;
}

export type IngestOptions = { force?: boolean };

/**
 * Full ingestion pass. Yields progress events so both the GUI (over SSE) and
 * the CLI can report the same thing.
 */
export async function* ingest(options: IngestOptions = {}): AsyncGenerator<IngestEvent> {
  const supabase = db();
  const { EMBED_CONCURRENCY } = env();

  const rows = await scanDocuments();

  if (options.force) {
    const ids = rows.filter((r) => r.sha256 !== "unsupported").map((r) => r.id);
    if (ids.length > 0) {
      await supabase.from("chunks").delete().in("document_id", ids);
      await supabase
        .from("documents")
        .update({ status: "pending", error: null, chunk_count: 0 })
        .in("id", ids);
      for (const row of rows) if (ids.includes(row.id)) row.status = "pending";
    }
  }

  const pending = rows.filter((row) => row.status === "pending");
  yield { type: "scan", total: rows.length, pending: pending.length };

  let embedded = 0;
  let failed = 0;
  const skipped = rows.length - pending.length;

  for (const row of pending) {
    yield { type: "document:start", relPath: row.rel_path, kind: row.media_kind };

    try {
      await supabase.from("documents").update({ status: "processing", error: null }).eq("id", row.id);

      const bytes = await fs.readFile(resolveInsideRoot(row.rel_path));
      const chunks = await split(row, bytes);

      if (chunks.length === 0) {
        throw new Error("File produced no embeddable content (is it empty?)");
      }
      yield { type: "document:chunks", relPath: row.rel_path, chunks: chunks.length };

      let done = 0;
      const vectors = await pool(chunks, EMBED_CONCURRENCY, async (chunk) => {
        const embedding = await embedOne(row, chunk);
        done++;
        return embedding;
      });
      yield { type: "document:progress", relPath: row.rel_path, done, total: chunks.length };

      await supabase.from("chunks").delete().eq("document_id", row.id);

      const records = chunks.map((chunk, index) => ({
        document_id: row.id,
        chunk_index: index,
        modality: chunk.modality,
        content: chunk.content.slice(0, 20000),
        meta: chunk.meta,
        embedding: vectors[index] as unknown as string,
      }));

      for (let i = 0; i < records.length; i += 20) {
        const { error } = await supabase.from("chunks").insert(records.slice(i, i + 20));
        if (error) throw new Error(`Insert failed: ${error.message}`);
      }

      await supabase
        .from("documents")
        .update({ status: "ready", chunk_count: chunks.length, error: null })
        .eq("id", row.id);

      embedded++;
      yield { type: "document:done", relPath: row.rel_path, chunks: chunks.length };
    } catch (error) {
      failed++;
      const message = error instanceof Error ? error.message : String(error);
      await supabase
        .from("documents")
        .update({ status: "error", error: message.slice(0, 1000) })
        .eq("id", row.id);
      yield { type: "document:error", relPath: row.rel_path, message };
    }
  }

  yield { type: "complete", embedded, skipped, failed };
}
