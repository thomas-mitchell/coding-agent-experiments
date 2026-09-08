export const KIND_ICON: Record<string, string> = {
  text: "TXT",
  image: "IMG",
  video: "VID",
  audio: "AUD",
  pdf: "PDF",
};

export const KINDS = ["text", "image", "video", "audio", "pdf"] as const;

export const STATUS_STYLE: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  processing: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  ready: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  error: "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}

export function fileUrl(relPath: string) {
  return `/api/files/${relPath.split("/").map(encodeURIComponent).join("/")}`;
}

export function clock(seconds: number) {
  const s = Math.round(seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
