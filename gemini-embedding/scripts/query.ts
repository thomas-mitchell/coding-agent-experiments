/**
 * Headless query: npm run query -- "your question here"
 *   --top-k=8        how many passages to retrieve
 *   --min=0.3        minimum cosine similarity
 *   --kinds=pdf,image  restrict to certain media types
 *   --raw            print retrieved passages only, skip the reasoning model
 */
import { config } from "dotenv";

config({ path: ".env.local" });
config({ path: ".env" });

function flag(name: string, fallback: string) {
  const match = process.argv.find((arg) => arg.startsWith(`--${name}=`));
  return match ? match.slice(name.length + 3) : fallback;
}

async function main() {
  const question = process.argv.slice(2).filter((arg) => !arg.startsWith("--")).join(" ");
  if (!question) {
    console.error('Usage: npm run query -- "your question"');
    process.exit(1);
  }

  const { retrieve } = await import("../src/lib/retrieve");
  const { reason } = await import("../src/lib/openai");
  const kinds = flag("kinds", "")
    .split(",")
    .map((k) => k.trim())
    .filter(Boolean);

  const results = await retrieve({
    question,
    topK: Number(flag("top-k", "8")),
    minSimilarity: Number(flag("min", "0")),
    kinds: kinds as never[],
  });

  console.log(`\nRetrieved ${results.length} passage(s):\n`);
  for (const [index, chunk] of results.entries()) {
    const position =
      chunk.meta?.page_start != null
        ? `pages ${chunk.meta.page_start}-${chunk.meta.page_end}`
        : chunk.meta?.start_sec != null
          ? `${chunk.meta.start_sec}s-${chunk.meta.end_sec}s`
          : `chunk ${chunk.chunk_index + 1}`;
    console.log(
      `[${index + 1}] ${chunk.similarity.toFixed(3)}  ${chunk.rel_path} (${chunk.media_kind}, ${position})`,
    );
    console.log(`    ${chunk.content.replace(/\s+/g, " ").slice(0, 220)}\n`);
  }

  if (process.argv.includes("--raw")) return;

  const { answer, model } = await reason(question, results);
  console.log(`--- answer (${model}) ---\n`);
  console.log(answer);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
