import { createBrowserClient } from "@supabase/ssr";

/**
 * Supabase client for code that runs in the browser. `createBrowserClient` is
 * already a singleton internally, so calling this repeatedly is free.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
}
