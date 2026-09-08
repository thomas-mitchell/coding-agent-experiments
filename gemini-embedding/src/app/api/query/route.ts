import { NextResponse } from "next/server";
import { retrieve } from "@/lib/retrieve";
import { reason } from "@/lib/openai";
import type { MediaKind } from "@/lib/types";

export const runtime = "nodejs";
export const maxDuration = 300;

const KINDS: MediaKind[] = ["text", "image", "video", "audio", "pdf"];

/**
 * POST /api/query - accepts JSON, or multipart when an image is used as the
 * query. Embeds the question, retrieves from pgvector, then asks the Codex
 * model to answer over the retrieved passages.
 */
export async function POST(request: Request) {
  try {
    const contentType = request.headers.get("content-type") ?? "";
    let question = "";
    let topK = 8;
    let minSimilarity = 0;
    let kinds: MediaKind[] = [];
    let effort: string | undefined;
    let image: { bytes: Buffer; mimeType: string } | undefined;

    if (contentType.includes("multipart/form-data")) {
      const form = await request.formData();
      question = String(form.get("question") ?? "");
      topK = Number(form.get("topK") ?? 8);
      minSimilarity = Number(form.get("minSimilarity") ?? 0);
      kinds = parseKinds(form.get("kinds"));
      effort = optionalString(form.get("effort"));
      const file = form.get("image");
      if (file instanceof File && file.size > 0) {
        image = {
          bytes: Buffer.from(await file.arrayBuffer()),
          mimeType: file.type || "image/png",
        };
      }
    } else {
      const body = await request.json();
      question = String(body.question ?? "");
      topK = Number(body.topK ?? 8);
      minSimilarity = Number(body.minSimilarity ?? 0);
      kinds = parseKinds(body.kinds);
      effort = optionalString(body.effort);
    }

    if (!question.trim() && !image) {
      return NextResponse.json({ error: "Ask a question or attach an image" }, { status: 400 });
    }

    const results = await retrieve({
      question,
      topK: clamp(topK, 1, 50),
      minSimilarity: clamp(minSimilarity, 0, 1),
      kinds,
      image,
    });

    // Retrieval is the part that must not be lost. If the reasoning model is
    // unavailable (no credits, rate limited, outage), still return the passages
    // and report the synthesis failure separately.
    try {
      const { answer, model } = await reason(
        question || "Describe the content most similar to the attached image.",
        results,
        effort,
      );
      return NextResponse.json({ answer, model, results });
    } catch (error) {
      return NextResponse.json({
        answer: null,
        answerError: error instanceof Error ? error.message : String(error),
        results,
      });
    }
  } catch (error) {
    const text = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: text }, { status: 500 });
  }
}

function parseKinds(value: unknown): MediaKind[] {
  const list =
    typeof value === "string" ? value.split(",") : Array.isArray(value) ? value.map(String) : [];
  return list.map((v) => v.trim()).filter((v): v is MediaKind => KINDS.includes(v as MediaKind));
}

function optionalString(value: unknown) {
  const text = typeof value === "string" ? value.trim() : "";
  return text || undefined;
}

function clamp(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min;
  return Math.min(Math.max(value, min), max);
}
