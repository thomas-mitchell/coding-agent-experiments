"use client";

import { useRef, useState } from "react";

import { ChevronDownIcon, ChevronRightIcon, SlidersIcon } from "@/components/icons";
import { ResultCard } from "@/components/result-card";
import { UploadCard } from "@/components/upload-card";
import { generateTryOn } from "@/lib/try-on";
import { useObjectUrl } from "@/lib/use-object-url";

const BREADCRUMBS = ["Men", "Accessories", "Virtual Try-On"];

export function TryOnStudio() {
  const [image1, setImage1] = useState<File | null>(null);
  const [image2, setImage2] = useState<File | null>(null);
  const [result, setResult] = useState<Blob | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Previews and the result URL are derived from their blobs, so every object
  // URL is revoked automatically when it is replaced or the page unmounts.
  const image1Preview = useObjectUrl(image1);
  const image2Preview = useObjectUrl(image2);
  const resultUrl = useObjectUrl(result);

  // Guards against a second submit landing while one is in flight -- state
  // updates are async, so `isLoading` alone can still let a double-click past.
  const inFlight = useRef(false);

  const canGenerate = Boolean(image1 && image2) && !isLoading;

  async function handleGenerate() {
    if (!image1 || !image2 || inFlight.current) return;

    inFlight.current = true;
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
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
    <main className="mx-auto w-full max-w-[1320px] px-6 pb-24 pt-9">
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-[13px]">
        {BREADCRUMBS.map((crumb, position) => {
          const isLast = position === BREADCRUMBS.length - 1;
          return (
            <span key={crumb} className="flex items-center gap-2">
              <span className={isLast ? "text-subtle/70" : "text-ink"}>{crumb}</span>
              {!isLast && <ChevronRightIcon className="h-3 w-3 text-subtle/60" />}
            </span>
          );
        })}
      </nav>

      <h1 className="mt-5 text-[38px] font-bold leading-none tracking-[-0.02em] sm:text-[46px]">
        Virtual Try-On
      </h1>

      {/*
        The reference's black FILTER BY block is the strongest element on the
        page, so the primary action takes its place rather than leaving it as
        dead decoration.
      */}
      <div className="mt-9 flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 items-stretch">
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
                Generate try-on
                <SlidersIcon className="h-4 w-4" />
              </>
            )}
          </button>
          <div className="chrome-label hidden items-center gap-3 border border-l-0 border-hairline px-6 text-ink sm:flex">
            Hat on mannequin
            <ChevronDownIcon className="h-3.5 w-3.5" />
          </div>
        </div>

        <p className="text-[13px] text-subtle" role="status">
          {statusLine({ image1, image2, isLoading, hasResult: Boolean(result) })}
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
        <UploadCard
          index="01"
          title="Person"
          hint="A clear photo of the person or mannequin wearing the base look."
          file={image1}
          previewUrl={image1Preview}
          disabled={isLoading}
          onSelect={(file) => {
            setError(null);
            setImage1(file);
          }}
          onClear={() => setImage1(null)}
          onReject={setError}
        />
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
  image1,
  image2,
  isLoading,
  hasResult,
}: {
  image1: File | null;
  image2: File | null;
  isLoading: boolean;
  hasResult: boolean;
}): string {
  if (isLoading) return "Generating, this usually takes around 25 seconds";
  if (hasResult) return "1 result";
  const count = [image1, image2].filter(Boolean).length;
  if (count === 2) return "2 of 2 images ready";
  return `${count} of 2 images selected`;
}
