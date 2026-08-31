/*
 * Hand-rolled so the UI does not drag in an icon dependency for three glyphs.
 * All of them inherit `currentColor` and size from the caller.
 */
type IconProps = { className?: string };

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  viewBox: "0 0 24 24",
  "aria-hidden": true,
} as const;

export function CloseIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function SlidersIcon({ className }: IconProps) {
  return (
    <svg {...base} className={className}>
      <path d="M8 4v10M8 18v2M16 4v2M16 10v10" />
      <circle cx="8" cy="16" r="2" />
      <circle cx="16" cy="8" r="2" />
    </svg>
  );
}
