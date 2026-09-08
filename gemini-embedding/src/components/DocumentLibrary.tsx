"use client";

import { useRef, useState } from "react";
import type { DocumentRow } from "@/lib/types";
import { KIND_ICON, STATUS_STYLE, formatBytes } from "./shared";

type Props = {
  documents: DocumentRow[];
  busy: boolean;
  progress: string[];
  onUpload: (files: FileList) => void;
  onEmbed: (force: boolean) => void;
  onRescan: () => void;
  onDelete: (id: string) => void;
};

export default function DocumentLibrary({
  documents,
  busy,
  progress,
  onUpload,
  onEmbed,
  onRescan,
  onDelete,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const pending = documents.filter((d) => d.status === "pending").length;
  const chunks = documents.reduce((sum, d) => sum + d.chunk_count, 0);

  return (
    <aside className="flex h-full w-full flex-col gap-4 border-r border-[var(--color-edge)] bg-[var(--color-panel)] p-5 lg:w-[380px] lg:shrink-0">
      <header>
        <h1 className="text-base font-semibold">Document library</h1>
        <p className="mt-1 text-xs text-[var(--color-muted)]">
          Files live in <code className="text-[var(--color-accent)]">documents/</code>. Drop them
          here or copy them into that folder directly.
        </p>
      </header>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (e.dataTransfer.files.length) onUpload(e.dataTransfer.files);
        }}
        onClick={() => input.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition ${
          dragging
            ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
            : "border-[var(--color-edge)] hover:border-[var(--color-accent)]/60"
        }`}
      >
        <p className="text-sm font-medium">Drop files to upload</p>
        <p className="mt-1 text-xs text-[var(--color-muted)]">
          text &middot; images &middot; audio &middot; video &middot; PDF
        </p>
        <input
          ref={input}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && onUpload(e.target.files)}
        />
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onEmbed(false)}
          disabled={busy}
          className="flex-1 rounded-lg bg-[var(--color-accent)] px-3 py-2 text-sm font-semibold text-[#0b0d12] transition hover:brightness-110 disabled:opacity-40"
        >
          {busy ? "Embedding…" : `Embed${pending ? ` (${pending})` : ""}`}
        </button>
        <button
          onClick={onRescan}
          disabled={busy}
          className="rounded-lg border border-[var(--color-edge)] px-3 py-2 text-sm transition hover:border-[var(--color-accent)]/60 disabled:opacity-40"
          title="Re-read the documents/ folder"
        >
          Rescan
        </button>
        <button
          onClick={() => onEmbed(true)}
          disabled={busy}
          className="rounded-lg border border-[var(--color-edge)] px-3 py-2 text-sm transition hover:border-[var(--color-accent)]/60 disabled:opacity-40"
          title="Delete every vector and re-embed from scratch"
        >
          Re-embed all
        </button>
      </div>

      {progress.length > 0 && (
        <pre className="max-h-40 overflow-auto rounded-lg border border-[var(--color-edge)] bg-black/30 p-3 text-[11px] leading-relaxed text-[var(--color-muted)]">
          {progress.join("\n")}
        </pre>
      )}

      <div className="flex items-center justify-between text-xs text-[var(--color-muted)]">
        <span>
          {documents.length} document{documents.length === 1 ? "" : "s"}
        </span>
        <span>{chunks} vectors</span>
      </div>

      <ul className="flex-1 space-y-2 overflow-auto">
        {documents.length === 0 && (
          <li className="rounded-lg border border-dashed border-[var(--color-edge)] p-4 text-center text-xs text-[var(--color-muted)]">
            Nothing indexed yet.
          </li>
        )}
        {documents.map((doc) => (
          <li
            key={doc.id}
            className="group rounded-lg border border-[var(--color-edge)] bg-black/20 p-3"
          >
            <div className="flex items-start gap-2">
              <span className="mt-0.5 rounded bg-[var(--color-edge)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-muted)]">
                {KIND_ICON[doc.media_kind]}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm" title={doc.rel_path}>
                  {doc.rel_path}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-[var(--color-muted)]">
                  <span
                    className={`rounded border px-1.5 py-px ${STATUS_STYLE[doc.status] ?? ""}`}
                  >
                    {doc.status}
                  </span>
                  <span>{formatBytes(doc.size_bytes)}</span>
                  {doc.chunk_count > 0 && <span>{doc.chunk_count} chunks</span>}
                </div>
                {doc.error && (
                  <p className="mt-1.5 text-[11px] text-rose-300/90 break-words">{doc.error}</p>
                )}
              </div>
              <button
                onClick={() => onDelete(doc.id)}
                className="opacity-0 transition group-hover:opacity-100 text-[var(--color-muted)] hover:text-rose-300"
                title="Delete file and its vectors"
              >
                ✕
              </button>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
