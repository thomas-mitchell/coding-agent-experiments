"use client";

import { useRef, useState } from "react";

import { SlidersIcon } from "@/components/icons";
import { PersonCard } from "@/components/person-card";
import { ResultCard } from "@/components/result-card";
import { UploadCard } from "@/components/upload-card";
import { generateTryOn, loadPersonImage } from "@/lib/try-on";
import { useObjectUrl } from "@/lib/use-object-url";

export function TryOnStudio() {
  // Only the garment is chosen by the user; the person image is fixed.
  const [image2, setImage2] = useState<File | null>(null);
  const [result, setResult] = useState<Blob | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Previews and the result URL are derived from their blobs, so every object
  // URL is revoked automatically when it is replaced or the page unmounts.
  const image2Preview = useObjectUrl(image2);
  const resultUrl = useObjectUrl(result);

  // Guards against a second submit landing while one is in flight -- state
  // updates are async, so `isLoading` alone can still let a double-click past.
  const inFlight = useRef(false);

  const canGenerate = Boolean(image2) && !isLoading;

  async function handleGenerate() {
    if (!image2 || inFlight.current) return;

    inFlight.current = true;
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      // Fetched per run rather than held in state: the browser caches it
      // after the first request, and this keeps a failed fetch reportable
      // through the same error path as the generation itself.
      const image1 = await loadPersonImage();
      setResult(await generateTryOn(image1, image2));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Something went wrong reaching the try-on service.",
      );
    } finally {
      setIsLoading(false);
      inFlight.current = false;
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1320px] px-6 pb-24 pt-12">
      <h1 className="sr-only">Kenji&rsquo;s modelling gig</h1>

      <p className="mx-auto max-w-[680px] text-center text-[15px] leading-relaxed text-subtle">
        Detective work has been a little slow lately, so Kenji has been doing a
        little fashion modelling to earn some extra money.
      </p>

      {/*
        The reference's black FILTER BY block is the strongest element on the
        page, so the primary action takes its place rather than leaving it as
        dead decoration.
      */}
      <div className="mt-8 flex flex-wrap items-center justify-between gap-4">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={!canGenerate}
          className="chrome-label flex items-center gap-3 bg-ink px-8 py-4 text-white transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {isLoading ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              Generating&hellip;
            </>
          ) : (
            <>
              Try it on Kenji!
              <SlidersIcon className="h-4 w-4" />
            </>
          )}
        </button>

        <p className="text-[13px] text-subtle" role="status">
          {statusLine({ image2, isLoading, hasResult: Boolean(result) })}
        </p>
      </div>

      {error && (
        <p
          role="alert"
          className="mt-4 border border-hairline border-l-2 border-l-ink bg-fill px-4 py-3 text-[12px] leading-relaxed text-ink"
        >
          {error}
        </p>
      )}

      <div className="mt-6 grid grid-cols-1 gap-8 md:grid-cols-3">
        <PersonCard />
        <UploadCard
          index="02"
          title="Garment"
          hint="The item to try on, ideally shot flat or on a plain background."
          file={image2}
          previewUrl={image2Preview}
          disabled={isLoading}
          onSelect={(file) => {
            setError(null);
            setImage2(file);
          }}
          onClear={() => setImage2(null)}
          onReject={setError}
        />
        <ResultCard imageUrl={resultUrl} isLoading={isLoading} error={error} />
      </div>
    </main>
  );
}

function statusLine({
  image2,
  isLoading,
  hasResult,
}: {
  image2: File | null;
  isLoading: boolean;
  hasResult: boolean;
}): string {
  if (isLoading) return "Generating, this usually takes around 25 seconds";
  if (hasResult) return "1 result";
  return image2 ? "Ready to generate" : "Select a garment to begin";
}
