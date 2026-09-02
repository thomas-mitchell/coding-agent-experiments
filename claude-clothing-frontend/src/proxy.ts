import { type NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/proxy";

// Next.js 16 renamed `middleware.ts` to `proxy.ts`; the export name changed to
// match. See node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md.
export async function proxy(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Everything except static assets. The image exclusion matters here: the
     * try-on flow fetches /kenji.png from the browser at run time.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
