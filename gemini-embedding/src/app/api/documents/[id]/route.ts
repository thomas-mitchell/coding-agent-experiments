import { NextResponse } from "next/server";
import fs from "node:fs/promises";
import { db } from "@/lib/supabase";
import { resolveInsideRoot } from "@/lib/paths";

export const runtime = "nodejs";

/** Delete a document: its chunks (via cascade), its row, and the file on disk. */
export async function DELETE(_request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    const supabase = db();

    const { data: row, error } = await supabase
      .from("documents")
      .select("rel_path")
      .eq("id", id)
      .single();
    if (error) throw new Error(error.message);

    await fs.rm(resolveInsideRoot(row.rel_path), { force: true });

    const { error: deleteError } = await supabase.from("documents").delete().eq("id", id);
    if (deleteError) throw new Error(deleteError.message);

    return NextResponse.json({ ok: true });
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: text }, { status: 500 });
  }
}
