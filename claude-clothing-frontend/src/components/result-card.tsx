"use client";

import { useEffect, useState } from "react";

type ResultCardProps = {
  imageUrl: string | null;
  isLoading: boolean;
  error: string | null;
};

export function ResultCard({ imageUrl, isLoading, error }: ResultCardProps) {
  return (
    <div className="flex flex-col">
      <div className="relative aspect-[3/4] w-full overflow-hidden border border-hairline bg-fill">
        {isLoading && <LoadingState />}

        {!isLoading && imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt="Generated virtual try-on result"
            className="absolute inset-0 h-full w-full object-contain"
          />
        )}

        {!isLoading && !imageUrl && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center">
            {error ? (
              <>
                <span className="chrome-label text-ink">Generation failed</span>
                <p className="max-w-[260px] text-[11px] leading-relaxed text-subtle">
                  {error}
                </p>
              </>
            ) : (
              <>
                <span className="chrome-label text-ink">Your result</span>
                <p className="max-w-[220px] text-[11px] leading-relaxed text-subtle">
                  Choose a garment, then generate to see the composite here.
                </p>
              </>
            )}
          </div>
        )}
      </div>

      <div className="mt-3 flex items-baseline justify-between gap-3">
        <span className="chrome-label">03 &mdash; Result</span>
        <span className="text-[11px] text-subtle">
          {isLoading ? "Generating" : imageUrl ? "Ready" : error ? "Error" : "Awaiting input"}
        </span>
      </div>
    </div>
  );
}

/**
 * The measured round trip is ~25s, which is long enough that a static skeleton
 * reads as a hung page. The elapsed counter is the cheapest way to show the
 * request is still alive.
 */
function LoadingState() {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => {
      setSeconds(Math.floor((Date.now() - started) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-fill">
      <div className="absolute inset-0 animate-pulse bg-hairline/60" />
      <span
        className="relative h-8 w-8 animate-spin rounded-full border-2 border-hairline border-t-ink"
        role="status"
        aria-label="Generating result"
      />
      <span className="chrome-label relative text-subtle tabular-nums">
        Generating &middot; {seconds}s
      </span>
    </div>
  );
}
