import { NextResponse } from "next/server";
import { db } from "@/lib/supabase";
import { scanDocuments } from "@/lib/ingest/scan";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * GET /api/documents        - list what the database knows about
 * GET /api/documents?scan=1 - reconcile the documents/ folder first
 */
export async function GET(request: Request) {
  try {
    const shouldScan = new URL(request.url).searchParams.get("scan") === "1";
    if (shouldScan) {
      return NextResponse.json({ documents: await scanDocuments() });
    }
    const { data, error } = await db()
      .from("documents")
      .select("*")
      .order("created_at", { ascending: true });
    if (error) throw new Error(error.message);
    return NextResponse.json({ documents: data ?? [] });
  } catch (error) {
    return NextResponse.json({ error: message(error) }, { status: 500 });
  }
}

function message(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
