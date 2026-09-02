import "server-only";

import { createClient as createSupabaseClient } from "@supabase/supabase-js";

/**
 * Service-role client. Bypasses row-level security entirely, so it exists for
 * exactly one job: writing the billing tables, which deliberately have no
 * insert/update policies (see the `add_billing` migration). A user must never
 * be able to grant themselves access, so the grant cannot run as the user.
 *
 * Built from `@supabase/supabase-js` rather than `@supabase/ssr`: there is no
 * session and no cookie jar here, and picking up the caller's cookies would
 * defeat the point.
 */
export function createAdminClient() {
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!key) {
    throw new Error(
      "SUPABASE_SECRET_KEY is not set. Copy the service_role key from the Supabase dashboard into .env and restart the dev server.",
    );
  }

  return createSupabaseClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, key, {
    // Nothing to persist or refresh: the key never expires and each call is a
    // one-shot server request.
    auth: { persistSession: false, autoRefreshToken: false },
  });
}
