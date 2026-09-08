"use client";

import type { MatchedChunk } from "@/lib/types";
import { KIND_ICON, clock, fileUrl } from "./shared";

export default function ResultCard({ chunk, index }: { chunk: MatchedChunk; index: number }) {
  const url = fileUrl(chunk.rel_path);
  const start = chunk.meta?.start_sec ?? 0;
  const position =
    chunk.meta?.page_start != null
      ? `pages ${chunk.meta.page_start}-${chunk.meta.page_end}`
      : chunk.meta?.start_sec != null
        ? `${clock(chunk.meta.start_sec)}-${clock(chunk.meta.end_sec ?? 0)}`
        : `chunk ${chunk.chunk_index + 1}`;

  return (
    <article
      id={`result-${index + 1}`}
      className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-4 target:border-[var(--color-accent)]"
    >
      <header className="flex flex-wrap items-center gap-2 text-xs text-[var(--color-muted)]">
        <span className="rounded bg-[var(--color-accent)]/15 px-1.5 py-0.5 font-mono text-[var(--color-accent)]">
          [{index + 1}]
        </span>
        <span className="rounded bg-[var(--color-edge)] px-1.5 py-0.5 font-mono text-[10px]">
          {KIND_ICON[chunk.media_kind]}
        </span>
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="truncate text-[#e7eaf3] underline decoration-dotted underline-offset-2"
        >
          {chunk.rel_path}
        </a>
        <span>| {position}</span>
        <span className="ml-auto font-mono text-[var(--color-accent)]">
          {chunk.similarity.toFixed(3)}
        </span>
      </header>

      <div className="mt-3">
        {chunk.media_kind === "image" && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={chunk.filename}
            className="max-h-72 rounded-lg border border-[var(--color-edge)]"
          />
        )}
        {chunk.media_kind === "video" && (
          <video
            src={`${url}#t=${start}`}
            controls
            preload="metadata"
            className="max-h-72 w-full rounded-lg border border-[var(--color-edge)]"
          />
        )}
        {chunk.media_kind === "audio" && (
          <audio src={`${url}#t=${start}`} controls preload="metadata" className="w-full" />
        )}
        {chunk.media_kind === "pdf" && (
          <a
            href={`${url}#page=${chunk.meta?.page_start ?? 1}`}
            target="_blank"
            rel="noreferrer"
            className="inline-block rounded-lg border border-[var(--color-edge)] px-3 py-1.5 text-xs text-[var(--color-accent)] hover:border-[var(--color-accent)]/60"
          >
            Open PDF at page {chunk.meta?.page_start ?? 1}
          </a>
        )}
      </div>

      {chunk.content && (
        <p className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap text-sm leading-relaxed text-[#c9cfdd]">
          {chunk.content}
        </p>
      )}
    </article>
  );
}
