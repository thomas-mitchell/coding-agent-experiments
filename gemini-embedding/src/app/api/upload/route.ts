import { NextResponse } from "next/server";
import fs from "node:fs/promises";
import path from "node:path";
import { documentsRoot, resolveInsideRoot, sanitizeFilename } from "@/lib/paths";

export const runtime = "nodejs";
export const maxDuration = 300;

/**
 * POST /api/upload - multipart form with one or more `files` entries.
 * Everything lands in the same documents/ folder that a manual drag-and-drop
 * would use, so the GUI and the filesystem are never out of sync.
 */
export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const files = form.getAll("files").filter((f): f is File => f instanceof File);
    if (files.length === 0) {
      return NextResponse.json({ error: "No files in request" }, { status: 400 });
    }

    await fs.mkdir(documentsRoot(), { recursive: true });

    const saved: string[] = [];
    for (const file of files) {
      const name = await uniqueName(sanitizeFilename(file.name));
      const target = resolveInsideRoot(name);
      await fs.writeFile(target, Buffer.from(await file.arrayBuffer()));
      saved.push(name);
    }

    return NextResponse.json({ saved });
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: text }, { status: 500 });
  }
}

/** Never silently overwrite an already-indexed file. */
async function uniqueName(name: string) {
  const ext = path.extname(name);
  const stem = name.slice(0, name.length - ext.length);
  let candidate = name;
  for (let n = 2; n < 1000; n++) {
    try {
      await fs.access(resolveInsideRoot(candidate));
      candidate = `${stem}-${n}${ext}`;
    } catch {
      return candidate;
    }
  }
  return `${stem}-${Date.now()}${ext}`;
}
