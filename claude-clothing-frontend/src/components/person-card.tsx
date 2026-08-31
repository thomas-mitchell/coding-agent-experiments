import Image from "next/image";

import { PERSON_IMAGE } from "@/lib/try-on";

/**
 * Card 01. Takes the slot the person uploader used to occupy and keeps the same
 * chrome -- frame, aspect ratio and caption row -- so the three-card grid still
 * reads as one set.
 */
export function PersonCard() {
  return (
    <div className="flex flex-col">
      <div className="relative aspect-[3/4] w-full overflow-hidden border border-hairline bg-fill">
        <Image
          src={PERSON_IMAGE.src}
          alt={PERSON_IMAGE.alt}
          fill
          sizes="(min-width: 768px) 33vw, 100vw"
          priority
          className="object-contain"
        />
      </div>

      <div className="mt-3 flex items-baseline justify-between gap-3">
        <span className="chrome-label">01 &mdash; Kenji</span>
        <span className="text-[11px] text-subtle">Fixed base image</span>
      </div>
    </div>
  );
}
