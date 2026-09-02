"use client";

import Image from "next/image";

import { GARMENT_PRESETS, type GarmentPreset } from "@/lib/try-on";

type GarmentPresetsProps = {
  selectedId: string | null;
  pendingId: string | null;
  disabled?: boolean;
  onSelect: (preset: GarmentPreset) => void;
};

/**
 * The shortcut into card 02: picking one of these fills the garment slot with
 * a bundled image instead of a file from disk. Rendered as radios rather than
 * buttons because that is what it is -- one of a set, exactly one active -- and
 * it gets arrow-key traversal and the selected state announced for free.
 */
export function GarmentPresets({
  selectedId,
  pendingId,
  disabled = false,
  onSelect,
}: GarmentPresetsProps) {
  return (
    <fieldset className="mt-6" disabled={disabled}>
      <legend className="chrome-label text-subtle">Or pick a garment</legend>

      <div className="mt-3 grid grid-cols-4 gap-2">
        {GARMENT_PRESETS.map((preset) => {
          const isSelected = preset.id === selectedId;
          const isPending = preset.id === pendingId;

          return (
            <label
              key={preset.id}
              title={preset.label}
              className={`relative block aspect-[3/4] cursor-pointer overflow-hidden border bg-fill transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ink has-[:focus-visible]:ring-offset-2 ${
                isSelected ? "border-ink" : "border-hairline hover:border-ink"
              } ${disabled ? "cursor-not-allowed opacity-40" : ""}`}
            >
              <input
                type="radio"
                name="garment-preset"
                value={preset.id}
                checked={isSelected}
                onChange={() => onSelect(preset)}
                className="sr-only"
              />
              <Image
                src={preset.src}
                alt={preset.alt}
                fill
                sizes="120px"
                className="object-cover"
              />
              <span className="sr-only">{preset.label}</span>

              {isPending && (
                <span className="absolute inset-0 flex items-center justify-center bg-white/70">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-hairline border-t-ink" />
                </span>
              )}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
