"use client";

import { useRef } from "react";
import { KINDS } from "./shared";

export type QuerySettings = {
  question: string;
  topK: number;
  minSimilarity: number;
  kinds: string[];
  effort: string;
};

type Props = {
  settings: QuerySettings;
  onChange: (patch: Partial<QuerySettings>) => void;
  onSubmit: () => void;
  imageFile: File | null;
  onImageChange: (file: File | null) => void;
  busy: boolean;
};

export default function QueryPanel({
  settings,
  onChange,
  onSubmit,
  imageFile,
  onImageChange,
  busy,
}: Props) {
  const imageInput = useRef<HTMLInputElement>(null);

  const toggleKind = (kind: string) =>
    onChange({
      kinds: settings.kinds.includes(kind)
        ? settings.kinds.filter((k) => k !== kind)
        : [...settings.kinds, kind],
    });

  return (
    <section className="rounded-xl border border-[var(--color-edge)] bg-[var(--color-panel)] p-5">
      <textarea
        value={settings.question}
        onChange={(e) => onChange({ question: e.target.value })}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) onSubmit();
        }}
        rows={3}
        placeholder="Ask a question about your indexed content...  (Ctrl+Enter to run)"
        className="w-full resize-y rounded-lg border border-[var(--color-edge)] bg-black/30 p-3 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]"
      />

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="text-xs text-[var(--color-muted)]">
          Results: <span className="text-[#e7eaf3]">{settings.topK}</span>
          <input
            type="range"
            min={1}
            max={25}
            value={settings.topK}
            onChange={(e) => onChange({ topK: Number(e.target.value) })}
            className="mt-1 w-full accent-[var(--color-accent)]"
          />
        </label>
        <label className="text-xs text-[var(--color-muted)]">
          Min similarity:{" "}
          <span className="text-[#e7eaf3]">{settings.minSimilarity.toFixed(2)}</span>
          <input
            type="range"
            min={0}
            max={0.95}
            step={0.05}
            value={settings.minSimilarity}
            onChange={(e) => onChange({ minSimilarity: Number(e.target.value) })}
            className="mt-1 w-full accent-[var(--color-accent)]"
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-xs text-[var(--color-muted)]">Filter:</span>
        {KINDS.map((kind) => {
          const active = settings.kinds.includes(kind);
          return (
            <button
              key={kind}
              onClick={() => toggleKind(kind)}
              className={`rounded-full border px-2.5 py-1 text-xs transition ${
                active
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                  : "border-[var(--color-edge)] text-[var(--color-muted)] hover:border-[var(--color-accent)]/50"
              }`}
            >
              {kind}
            </button>
          );
        })}
        {settings.kinds.length > 0 && (
          <button
            onClick={() => onChange({ kinds: [] })}
            className="text-xs text-[var(--color-muted)] underline hover:text-[#e7eaf3]"
          >
            clear
          </button>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="text-xs text-[var(--color-muted)]">
          Reasoning effort{" "}
          <select
            value={settings.effort}
            onChange={(e) => onChange({ effort: e.target.value })}
            className="ml-1 rounded border border-[var(--color-edge)] bg-black/30 px-2 py-1 text-xs text-[#e7eaf3] outline-none"
          >
            {["low", "medium", "high", "xhigh"].map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>
        </label>

        <button
          onClick={() => imageInput.current?.click()}
          className="rounded border border-[var(--color-edge)] px-2.5 py-1 text-xs text-[var(--color-muted)] transition hover:border-[var(--color-accent)]/60"
          title="Search by image instead of text (cross-modal retrieval)"
        >
          {imageFile ? `image: ${imageFile.name}` : "+ image query"}
        </button>
        {imageFile && (
          <button
            onClick={() => {
              onImageChange(null);
              if (imageInput.current) imageInput.current.value = "";
            }}
            className="text-xs text-[var(--color-muted)] underline hover:text-[#e7eaf3]"
          >
            remove
          </button>
        )}
        <input
          ref={imageInput}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => onImageChange(e.target.files?.[0] ?? null)}
        />

        <button
          onClick={onSubmit}
          disabled={busy}
          className="ml-auto rounded-lg bg-[var(--color-accent)] px-5 py-2 text-sm font-semibold text-[#0b0d12] transition hover:brightness-110 disabled:opacity-40"
        >
          {busy ? "Thinking..." : "Search"}
        </button>
      </div>
    </section>
  );
}
