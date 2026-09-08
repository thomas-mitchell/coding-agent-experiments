/**
 * Headless ingestion: `npm run ingest` (add `-- --force` to re-embed everything).
 * Does exactly what the GUI's Embed button does, without the browser.
 */
import { config } from "dotenv";

config({ path: ".env.local" });
config({ path: ".env" });

const force = process.argv.includes("--force");

async function main() {
  // Imported after dotenv so env validation sees the loaded values.
  const { ingest } = await import("../src/lib/ingest/run");

  let failed = 0;
  for await (const event of ingest({ force })) {
    switch (event.type) {
      case "scan":
        console.log(`Scanned ${event.total} document(s); ${event.pending} need embedding.`);
        break;
      case "document:start":
        console.log(`\n${event.relPath}  (${event.kind})`);
        break;
      case "document:chunks":
        console.log(`  split into ${event.chunks} chunk(s)`);
        break;
      case "document:done":
        console.log(`  stored ${event.chunks} vector(s)`);
        break;
      case "document:error":
        failed++;
        console.error(`  FAILED: ${event.message}`);
        break;
      case "complete":
        console.log(
          `\nDone. ${event.embedded} embedded, ${event.skipped} unchanged, ${event.failed} failed.`,
        );
        break;
    }
  }

  process.exit(failed > 0 ? 1 : 0);
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
