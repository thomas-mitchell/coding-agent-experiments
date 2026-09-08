"use client";

import { useCallback, useEffect, useState } from "react";
import type { DocumentRow, IngestEvent, MatchedChunk } from "@/lib/types";
import DocumentLibrary from "./DocumentLibrary";
import QueryPanel, { type QuerySettings } from "./QueryPanel";
import ResultCard from "./ResultCard";

type Answer = {
  answer: string | null;
  answerError?: string;
  model?: string;
  results: MatchedChunk[];
};

export default function RagApp() {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [ingesting, setIngesting] = useState(false);
  const [progress, setProgress] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<QuerySettings>({
    question: "",
    topK: 8,
    minSimilarity: 0,
    kinds: [],
    effort: "medium",
  });

  const loadDocuments = useCallback(async (scan = false) => {
    try {
      const response = await fetch(`/api/documents${scan ? "?scan=1" : ""}`);
      const body = await response.json();
      if (!response.ok) throw new Error(body.error ?? "Failed to load documents");
      setDocuments(body.documents);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void loadDocuments(true);
  }, [loadDocuments]);

  const upload = async (files: FileList) => {
    const form = new FormData();
    for (const file of Array.from(files)) form.append("files", file);
    setProgress((p) => [...p, `uploading ${files.length} file(s)...`]);
    try {
      const response = await fetch("/api/upload", { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error ?? "Upload failed");
      setProgress((p) => [...p, `saved: ${body.saved.join(", ")}`]);
      await loadDocuments(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  /** Consume the SSE progress stream from POST /api/ingest. */
  const embed = async (force: boolean) => {
    setIngesting(true);
    setProgress([]);
    setError(null);
    try {
      const response = await fetch(`/api/ingest${force ? "?force=1" : ""}`, { method: "POST" });
      if (!response.body) throw new Error("No response stream");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const messages = buffer.split("\n\n");
        buffer = messages.pop() ?? "";
        for (const message of messages) {
          const line = message.trim();
          if (!line.startsWith("data:")) continue;
          const event = JSON.parse(line.slice(5).trim()) as IngestEvent | { type: "fatal"; message: string };
          setProgress((p) => [...p, describe(event)]);
          if (event.type === "document:done" || event.type === "document:error") {
            void loadDocuments();
          }
          if (event.type === "fatal") setError(event.message);
        }
      }
      await loadDocuments();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIngesting(false);
    }
  };

  const remove = async (id: string) => {
    await fetch(`/api/documents/${id}`, { method: "DELETE" });
    await loadDocuments();
  };

  const search = async () => {
    if (!settings.question.trim() && !imageFile) return;
    setSearching(true);
    setError(null);
    setAnswer(null);
    try {
      let response: Response;
      if (imageFile) {
        const form = new FormData();
        form.append("question", settings.question);
        form.append("topK", String(settings.topK));
        form.append("minSimilarity", String(settings.minSimilarity));
        form.append("kinds", settings.kinds.join(","));
        form.append("effort", settings.effort);
        form.append("image", imageFile);
        response = await fetch("/api/query", { method: "POST", body: form });
      } else {
        response = await fetch("/api/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(settings),
        });
      }
      const body = await response.json();
      if (!response.ok) throw new Error(body.error ?? "Query failed");
      setAnswer(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSearching(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col lg:flex-row">
      <DocumentLibrary
        documents={documents}
        busy={ingesting}
        progress={progress}
        onUpload={upload}
        onEmbed={embed}
        onRescan={() => loadDocuments(true)}
        onDelete={remove}
      />

      <div className="flex-1 space-y-5 p-5 lg:p-8">
        <header>
          <h2 className="text-lg font-semibold">Multimodal RAG</h2>
          <p className="mt-1 text-xs text-[var(--color-muted)]">
            gemini-embedding-2 &rarr; Supabase pgvector &rarr; {answer?.model ?? "OpenAI Codex"}
          </p>
        </header>

        <QueryPanel
          settings={settings}
          onChange={(patch) => setSettings((s) => ({ ...s, ...patch }))}
          onSubmit={search}
          imageFile={imageFile}
          onImageChange={setImageFile}
          busy={searching}
        />

        {error && (
          <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 p-4 text-sm text-rose-200">
            {error}
          </div>
        )}

        {answer && (
          <>
            <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                Answer{answer.model ? ` · ${answer.model}` : ""}
              </h3>
              {answer.answer !== null ? (
                <div className="text-sm leading-relaxed">{renderAnswer(answer.answer)}</div>
              ) : (
                <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200">
                  <p className="font-medium">
                    Retrieval succeeded, but the reasoning model could not be reached.
                  </p>
                  <p className="mt-1 text-xs opacity-90">{answer.answerError}</p>
                  <p className="mt-2 text-xs opacity-90">
                    The retrieved passages below are still valid — only the written answer is
                    missing.
                  </p>
                </div>
              )}
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                Retrieved passages ({answer.results.length})
              </h3>
              {answer.results.map((chunk, index) => (
                <ResultCard key={chunk.chunk_id} chunk={chunk} index={index} />
              ))}
            </section>
          </>
        )}
      </div>
    </main>
  );
}

/**
 * The reasoning model answers in markdown. Rather than pull in a full markdown
 * renderer for the handful of constructs it actually emits, handle bold, inline
 * code, bullets and headings here - and turn [n] citations into links to the
 * matching result card.
 */
function renderAnswer(text: string) {
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];

  const flushBullets = () => {
    if (bullets.length === 0) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="my-2 ml-1 space-y-1.5">
        {bullets.map((item, index) => (
          <li key={index} className="flex gap-2">
            <span className="mt-[2px] text-[var(--color-accent)]">&bull;</span>
            <span>{inline(item)}</span>
          </li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  for (const line of lines) {
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    if (bullet) {
      bullets.push(bullet[1]);
      continue;
    }
    flushBullets();

    const heading = /^\s*#{1,6}\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push(
        <p key={`h-${blocks.length}`} className="mt-3 mb-1 font-semibold">
          {inline(heading[1])}
        </p>,
      );
      continue;
    }

    if (!line.trim()) {
      blocks.push(<div key={`sp-${blocks.length}`} className="h-2" />);
      continue;
    }
    blocks.push(
      <p key={`p-${blocks.length}`} className="my-1">
        {inline(line)}
      </p>,
    );
  }
  flushBullets();

  return blocks;
}

/** Inline markdown: **bold**, `code`, and [n] citation links. */
function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g).map((part, index) => {
    const citation = /^\[(\d+)\]$/.exec(part);
    if (citation) {
      return (
        <a
          key={index}
          href={`#result-${citation[1]}`}
          className="mx-0.5 rounded bg-[var(--color-accent)]/15 px-1 font-mono text-xs text-[var(--color-accent)] hover:bg-[var(--color-accent)]/30"
        >
          {part}
        </a>
      );
    }
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={index} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={index} className="rounded bg-black/40 px-1 py-px font-mono text-[13px]">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

function describe(event: IngestEvent | { type: "fatal"; message: string }) {
  switch (event.type) {
    case "scan":
      return `scanned ${event.total} document(s), ${event.pending} need embedding`;
    case "document:start":
      return `> ${event.relPath} (${event.kind})`;
    case "document:chunks":
      return `  split into ${event.chunks} chunk(s)`;
    case "document:progress":
      return `  embedded ${event.done}/${event.total}`;
    case "document:done":
      return `  done - ${event.chunks} vector(s) stored`;
    case "document:error":
      return `  FAILED: ${event.message}`;
    case "document:skip":
      return `  skipped: ${event.reason}`;
    case "complete":
      return `complete - ${event.embedded} embedded, ${event.skipped} unchanged, ${event.failed} failed`;
    case "fatal":
      return `FATAL: ${event.message}`;
  }
}
