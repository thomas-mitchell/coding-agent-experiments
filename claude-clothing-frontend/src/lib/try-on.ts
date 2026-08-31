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

/**
 * Fetches the base image and wraps it in a File.
 *
 * Deliberately requests the original asset rather than reusing whatever
 * `next/image` painted on screen: that is a resized, re-encoded variant served
 * from the optimiser, and the workflow should receive the full-quality source.
 * Returning a File (not a bare Blob) keeps the request identical in shape to
 * the one a user-picked image produced -- same `image1` field, same multipart
 * encoding, same filename metadata.
 */
export async function loadPersonImage(signal?: AbortSignal): Promise<File> {
  const response = await fetch(PERSON_IMAGE.src, { signal });
  if (!response.ok) {
    throw new Error(
      `Could not load the base image ${PERSON_IMAGE.src} (status ${response.status}).`,
    );
  }
  return new File([await response.blob()], PERSON_IMAGE.name, {
    type: PERSON_IMAGE.type,
  });
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
