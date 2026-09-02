/*
 * Transport layer for the n8n virtual try-on workflow.
 *
 * Verified against the live endpoint: a multipart POST carrying `image1` and
 * `image2` returns `200` with `content-type: image/jpeg` and takes ~25s.
 * Because that is slow, the browser calls n8n directly rather than hopping
 * through a Next route handler -- a Vercel function would sit near its
 * duration ceiling for the whole generation. CORS on the webhook reflects any
 * origin and allows POST, so the direct call needs no server cooperation.
 */

/*
 * Configured in `.env`, which is git-ignored -- `.env.example` carries the
 * placeholder. Note that NEXT_PUBLIC_ is inlined into the client bundle at
 * build time, so this keeps the URL out of version control but does not hide
 * it from anyone viewing the deployed page. Making it genuinely private means
 * moving the request behind a route handler and dropping the prefix.
 */
const WEBHOOK_URL = process.env.NEXT_PUBLIC_TRYON_WEBHOOK_URL;

/*
 * Read lazily rather than at module scope: an unset variable should surface as
 * a readable message when someone presses Generate, not as a module-evaluation
 * crash that blanks the whole page on load.
 */
function requireWebhookUrl(): string {
  if (!WEBHOOK_URL) {
    throw new Error(
      "No try-on endpoint is configured. Copy .env.example to .env and set NEXT_PUBLIC_TRYON_WEBHOOK_URL, then restart the dev server.",
    );
  }
  return WEBHOOK_URL;
}

/*
 * The person half of the composite is fixed rather than uploaded: one base
 * figure served straight from /public.
 */
export const PERSON_IMAGE = {
  src: "/kenji.png",
  name: "kenji.png",
  type: "image/png",
  alt: "Kenji, the fixed base figure used for every try-on",
} as const;

/*
 * Ready-made garments served from /public, offered alongside the uploader so
 * the tool is usable without hunting for a product shot first.
 */
export type GarmentPreset = {
  id: string;
  src: string;
  name: string;
  type: string;
  label: string;
  alt: string;
};

export const GARMENT_PRESETS: readonly GarmentPreset[] = [
  {
    id: "jacket01",
    src: "/clothing/jacket01.webp",
    name: "jacket01.webp",
    type: "image/webp",
    label: "Shearling jacket",
    alt: "Brown suede trucker jacket with a cream shearling lining",
  },
  {
    id: "jacket02",
    src: "/clothing/jacket02.jpg",
    name: "jacket02.jpg",
    type: "image/jpeg",
    label: "Puffer jacket",
    alt: "Orange quilted down puffer jacket worn open",
  },
  {
    id: "suit01",
    src: "/clothing/suit01.webp",
    name: "suit01.webp",
    type: "image/webp",
    label: "Grey suit",
    alt: "Grey pinstripe two-piece suit with a white shirt and burgundy tie",
  },
  {
    id: "suit02",
    src: "/clothing/suit02.jpg",
    name: "suit02.jpg",
    type: "image/jpeg",
    label: "Cream suit",
    alt: "Cream single-breasted suit jacket with a white shirt and tie",
  },
] as const;

/**
 * Fetches an asset from /public and wraps it in a File.
 *
 * Deliberately requests the original asset rather than reusing whatever
 * `next/image` painted on screen: that is a resized, re-encoded variant served
 * from the optimiser, and the workflow should receive the full-quality source.
 * Returning a File (not a bare Blob) keeps the request identical in shape to
 * the one a user-picked image produced -- same multipart encoding, same
 * filename metadata -- so nothing downstream cares where the image came from.
 */
async function loadPublicImage(
  asset: { src: string; name: string; type: string },
  signal?: AbortSignal,
): Promise<File> {
  const response = await fetch(asset.src, { signal });
  if (!response.ok) {
    throw new Error(
      `Could not load the image ${asset.src} (status ${response.status}).`,
    );
  }
  return new File([await response.blob()], asset.name, { type: asset.type });
}

/** Loads the fixed person half of the composite. */
export function loadPersonImage(signal?: AbortSignal): Promise<File> {
  return loadPublicImage(PERSON_IMAGE, signal);
}

/** Loads one of the built-in garments as though the user had picked it. */
export function loadGarmentPreset(
  preset: GarmentPreset,
  signal?: AbortSignal,
): Promise<File> {
  return loadPublicImage(preset, signal);
}

export const ACCEPTED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const ACCEPT_ATTRIBUTE = ACCEPTED_MIME_TYPES.join(",");
export const MAX_FILE_BYTES = 10 * 1024 * 1024;

/** Returns an error message, or null when the file is usable. */
export function validateImageFile(file: File): string | null {
  // `accept` on the input only filters the picker's dialog, and a drag-and-drop
  // bypasses it entirely, so both entry points funnel through here.
  if (!ACCEPTED_MIME_TYPES.includes(file.type)) {
    return `${file.name} is not a supported image. Use JPG, PNG or WebP.`;
  }
  if (file.size > MAX_FILE_BYTES) {
    return `${file.name} is ${formatBytes(file.size)}. The limit is ${formatBytes(MAX_FILE_BYTES)}.`;
  }
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Posts both images to the workflow and resolves with the generated image.
 *
 * Always resolves to a Blob, even on the JSON-shaped fallbacks, so the caller
 * has exactly one object-URL lifecycle to manage.
 */
export async function generateTryOn(
  image1: File,
  image2: File,
  signal?: AbortSignal,
): Promise<Blob> {
  const formData = new FormData();
  // These field names are the workflow's binary property names -- renaming
  // either one makes n8n fail to find the image.
  formData.append("image1", image1);
  formData.append("image2", image2);

  const response = await fetch(requireWebhookUrl(), {
    method: "POST",
    body: formData,
    signal,
    // No Content-Type header: fetch derives it from the FormData along with the
    // multipart boundary. Setting it by hand drops the boundary and n8n then
    // cannot parse the body at all.
  });

  if (!response.ok) {
    throw new Error(await describeFailure(response));
  }

  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.startsWith("image/")) {
    return response.blob();
  }

  // The live endpoint returns a raw image today. These branches keep a workflow
  // tweak (say, switching the Respond node to JSON) from silently rendering a
  // broken image instead of raising something readable.
  if (contentType.includes("application/json")) {
    return blobFromJsonPayload(await response.json(), signal);
  }

  throw new Error(`The workflow returned an unexpected response type: ${contentType || "unknown"}.`);
}

async function blobFromJsonPayload(payload: unknown, signal?: AbortSignal): Promise<Blob> {
  const record = (Array.isArray(payload) ? payload[0] : payload) as
    | Record<string, unknown>
    | undefined;

  if (record && typeof record === "object") {
    const mimeType =
      typeof record.mimeType === "string" ? record.mimeType : "image/jpeg";

    const base64 = firstString(record.data, record.base64, record.image);
    if (base64) {
      const response = await fetch(`data:${mimeType};base64,${stripDataPrefix(base64)}`);
      return response.blob();
    }

    const url = firstString(record.url, record.imageUrl, record.fileUrl);
    if (url) {
      const response = await fetch(url, { signal });
      if (!response.ok) throw new Error("The workflow returned an image URL that could not be fetched.");
      return response.blob();
    }
  }

  throw new Error("The workflow returned JSON with no image in it.");
}

function firstString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.length > 0) return value;
  }
  return null;
}

function stripDataPrefix(value: string): string {
  const comma = value.indexOf(",");
  return value.startsWith("data:") && comma !== -1 ? value.slice(comma + 1) : value;
}

/** n8n puts a usable reason in the error body; a bare "failed" would waste it. */
async function describeFailure(response: Response): Promise<string> {
  let detail = "";
  try {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text) as Record<string, unknown>;
      detail = firstString(parsed.message, parsed.error, parsed.hint) ?? text;
    } catch {
      detail = text;
    }
  } catch {
    // Body already consumed or unreadable -- fall through to the bare status.
  }

  detail = detail.trim().slice(0, 300);
  return detail
    ? `Generation failed (${response.status}): ${detail}`
    : `Generation failed with status ${response.status}.`;
}
