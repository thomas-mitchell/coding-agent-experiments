import "server-only";
import { db } from "./supabase";
import { embedQuery, embedQueryImage } from "./gemini";
import type { MatchedChunk, MediaKind } from "./types";

export type RetrieveOptions = {
  question: string;
  topK?: number;
  minSimilarity?: number;
  kinds?: MediaKind[];
  /** Optional image query - embedded into the same space for cross-modal search. */
  image?: { bytes: Buffer; mimeType: string };
};

export async function retrieve(options: RetrieveOptions): Promise<MatchedChunk[]> {
  const { question, topK = 8, minSimilarity = 0, kinds, image } = options;

  const embedding = image
    ? await embedQueryImage(image.bytes, image.mimeType)
    : await embedQuery(question);

  const { data, error } = await db().rpc("match_chunks", {
    query_embedding: embedding as unknown as string,
    match_count: topK,
    min_similarity: minSimilarity,
    filter_kinds: kinds && kinds.length > 0 ? kinds : null,
  });

  if (error) throw new Error(`Retrieval failed: ${error.message}`);
  return (data ?? []) as MatchedChunk[];
}
