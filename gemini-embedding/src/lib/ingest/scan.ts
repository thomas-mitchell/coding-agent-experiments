import "server-only";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { db } from "../supabase";
import { classify } from "../media";
import { documentsRoot, toRelKey } from "../paths";
import type { DocumentRow } from "../types";

const IGNORED = new Set([".git", "node_modules", ".next", "__pycache__"]);

async function walk(dir: string, out: string[] = []) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith(".") || IGNORED.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(full, out);
    else if (entry.isFile()) out.push(full);
  }
  return out;
}

async function sha256(file: string) {
  const hash = crypto.createHash("sha256");
  hash.update(await fs.readFile(file));
  return hash.digest("hex");
}

/**
 * Reconcile the documents folder with the `documents` table:
 * new files are inserted as pending, edited files (changed hash) are reset to
 * pending and their old chunks dropped, and rows whose file has disappeared
 * are deleted along with their chunks.
 */
export async function scanDocuments(): Promise<DocumentRow[]> {
  const root = documentsRoot();
  await fs.mkdir(root, { recursive: true });

  const files = await walk(root);
  const supabase = db();

  const { data: existingRows, error: readError } = await supabase.from("documents").select("*");
  if (readError) throw new Error(`Failed to read documents: ${readError.message}`);
  const existing = new Map((existingRows ?? []).map((row) => [row.rel_path, row as DocumentRow]));

  const seen = new Set<string>();

  for (const file of files) {
    const relPath = toRelKey(file);
    seen.add(relPath);

    const kind = classify(file);
    if (!kind) {
      const stat = await fs.stat(file);
      await supabase.from("documents").upsert(
        {
          rel_path: relPath,
          filename: path.basename(file),
          mime_type: "application/octet-stream",
          media_kind: "text",
          size_bytes: stat.size,
          sha256: "unsupported",
          status: "error",
          error: `Unsupported file type "${path.extname(file) || "(none)"}" - gemini-embedding-2 accepts text, images, audio, video and PDF.`,
          chunk_count: 0,
        },
        { onConflict: "rel_path" },
      );
      continue;
    }

    const stat = await fs.stat(file);
    const hash = await sha256(file);
    const prior = existing.get(relPath);

    if (prior && prior.sha256 === hash && prior.status === "ready") continue;

    if (prior && prior.sha256 !== hash) {
      await supabase.from("chunks").delete().eq("document_id", prior.id);
    }

    const { error: upsertError } = await supabase.from("documents").upsert(
      {
        rel_path: relPath,
        filename: path.basename(file),
        mime_type: kind.mime,
        media_kind: kind.kind,
        size_bytes: stat.size,
        sha256: hash,
        status: "pending",
        error: null,
        chunk_count: 0,
      },
      { onConflict: "rel_path" },
    );
    if (upsertError) throw new Error(`Failed to record ${relPath}: ${upsertError.message}`);
  }

  const removed = [...existing.keys()].filter((relPath) => !seen.has(relPath));
  if (removed.length > 0) {
    await supabase.from("documents").delete().in("rel_path", removed);
  }

  const { data, error } = await supabase
    .from("documents")
    .select("*")
    .order("created_at", { ascending: true });
  if (error) throw new Error(`Failed to list documents: ${error.message}`);
  return (data ?? []) as DocumentRow[];
}
