"use client";

import { useId, useState, type DragEvent } from "react";

import { CloseIcon, PlusIcon } from "@/components/icons";
import { ACCEPT_ATTRIBUTE, formatBytes, validateImageFile } from "@/lib/try-on";

type UploadCardProps = {
  index: string;
  title: string;
  hint: string;
  file: File | null;
  previewUrl: string | null;
  disabled?: boolean;
  onSelect: (file: File) => void;
  onClear: () => void;
  onReject: (message: string) => void;
};

export function UploadCard({
  index,
  title,
  hint,
  file,
  previewUrl,
  disabled = false,
  onSelect,
  onClear,
  onReject,
}: UploadCardProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputId = useId();

  function accept(candidate: File | undefined) {
    if (!candidate) return;
    const problem = validateImageFile(candidate);
    if (problem) {
      onReject(problem);
      return;
    }
    onSelect(candidate);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    // Without preventDefault the browser navigates away to display the file.
    event.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    accept(event.dataTransfer.files[0]);
  }

  return (
    <div className="flex flex-col">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`group relative aspect-[3/4] w-full overflow-hidden border bg-fill transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ink has-[:focus-visible]:ring-offset-2 ${
          isDragging ? "border-ink bg-white" : "border-hairline"
        }`}
      >
        {previewUrl && (
          /*
           * `contain`, not `cover`: cropping would cut off the garment or the
           * subject's head, and judging fit is the entire point of the tool.
           * Plain <img> rather than next/image -- the source is a client-side
           * object URL with no dimensions known at build time.
           */
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={previewUrl}
            alt={`${title} preview`}
            className="absolute inset-0 h-full w-full object-contain"
          />
        )}

        {/*
          A <label> wrapping a visually hidden input gives click, keyboard and
          screen-reader activation for free -- no ref.click() plumbing.
        */}
        <label
          htmlFor={inputId}
          className={`absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center ${
            disabled ? "cursor-not-allowed" : "cursor-pointer"
          }`}
        >
          <input
            id={inputId}
            type="file"
            accept={ACCEPT_ATTRIBUTE}
            disabled={disabled}
            className="sr-only"
            onChange={(event) => {
              accept(event.target.files?.[0]);
              // Reset so picking the same file twice still fires a change event.
              event.target.value = "";
            }}
          />
          {!previewUrl && (
            <>
              <PlusIcon className="h-7 w-7 text-subtle transition-colors group-hover:text-ink" />
              <span className="chrome-label text-ink">{title}</span>
              <span className="max-w-[220px] text-[11px] leading-relaxed text-subtle">
                {hint}
              </span>
              <span className="chrome-label mt-2 text-subtle">
                Drag &amp; drop or click
              </span>
            </>
          )}
        </label>

        {previewUrl && !disabled && (
          /*
           * Sits outside the label, above it in z-order: a button nested in a
           * label would also re-trigger the file picker on click.
           */
          <button
            type="button"
            onClick={onClear}
            aria-label={`Remove ${title}`}
            className="absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center bg-white/85 text-ink backdrop-blur transition-colors hover:bg-white"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="mt-3 flex items-baseline justify-between gap-3">
        <span className="chrome-label">
          {index} &mdash; {title}
        </span>
        <span className="truncate text-[11px] text-subtle" title={file?.name}>
          {file ? `${file.name} · ${formatBytes(file.size)}` : "No file"}
        </span>
      </div>
    </div>
  );
}
