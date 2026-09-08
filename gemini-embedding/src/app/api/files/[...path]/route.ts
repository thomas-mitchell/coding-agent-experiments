import { NextResponse } from "next/server";
import fs from "node:fs/promises";
import { classify } from "@/lib/media";
import { resolveInsideRoot } from "@/lib/paths";

export const runtime = "nodejs";

/**
 * Serves a file from documents/ so the GUI can preview retrieved results.
 * resolveInsideRoot rejects anything that escapes the documents folder.
 */
export async function GET(_request: Request, context: { params: Promise<{ path: string[] }> }) {
  try {
    const { path: segments } = await context.params;
    const relPath = segments.map(decodeURIComponent).join("/");
    const absolute = resolveInsideRoot(relPath);

    const stat = await fs.stat(absolute);
    if (!stat.isFile()) return new NextResponse("Not found", { status: 404 });

    const bytes = await fs.readFile(absolute);
    return new NextResponse(new Uint8Array(bytes), {
      headers: {
        "Content-Type": classify(absolute)?.mime ?? "application/octet-stream",
        "Content-Length": String(stat.size),
        "Cache-Control": "private, max-age=60",
      },
    });
  } catch {
    return new NextResponse("Not found", { status: 404 });
  }
}
