import "server-only";
import { z } from "zod";

/**
 * Server-only environment. The `server-only` import above makes any accidental
 * client-side import a build error, so none of these secrets can be bundled
 * into browser JavaScript.
 */
const schema = z.object({
  GEMINI_API_KEY: z.string().min(1, "GEMINI_API_KEY is missing from .env.local"),
  OPENAI_API_KEY: z.string().min(1, "OPENAI_API_KEY is missing from .env.local"),
  SUPABASE_URL: z.string().url("SUPABASE_URL must be a full https:// URL"),
  SUPABASE_SERVICE_ROLE_KEY: z
    .string()
    .min(1, "SUPABASE_SERVICE_ROLE_KEY is missing from .env.local"),

  EMBEDDING_MODEL: z.string().default("gemini-embedding-2"),
  EMBEDDING_DIMENSIONS: z.coerce.number().int().positive().default(1536),
  OPENAI_MODEL: z.string().default("gpt-5.6-terra"),
  OPENAI_REASONING_EFFORT: z
    .enum(["low", "medium", "high", "xhigh"])
    .default("medium"),
  DOCUMENTS_DIR: z.string().default("documents"),
  EMBED_CONCURRENCY: z.coerce.number().int().positive().default(3),
});

let cached: z.infer<typeof schema> | null = null;

export function env() {
  if (cached) return cached;
  const parsed = schema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  - ${i.path.join(".") || "(root)"}: ${i.message}`)
      .join("\n");
    throw new Error(
      `Invalid environment configuration.\n${issues}\n\nCopy .env.example to .env.local and fill in the values.`,
    );
  }
  cached = parsed.data;
  return cached;
}
