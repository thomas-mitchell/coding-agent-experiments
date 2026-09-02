import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/** Routes reachable while signed out. Everything else redirects to /login. */
const PUBLIC_PREFIXES = ["/login", "/signup", "/auth"];

/**
 * Refreshes the Supabase auth token on every request and gates the app.
 *
 * Server components cannot write cookies, so this is the only place a rotated
 * token gets handed back to the browser. Two rules from the Supabase SSR guide
 * are load-bearing and easy to break:
 *   1. Run no code between `createServerClient` and `getClaims()`.
 *   2. Return `supabaseResponse` as-is; if you swap in another response, copy
 *      its cookies across first.
 * Breaking either logs users out at random.
 */
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet, headers) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
          // Cache headers that stop a CDN serving one user's session to another.
          Object.entries(headers).forEach(([key, value]) =>
            supabaseResponse.headers.set(key, value),
          );
        },
      },
    },
  );

  // getClaims() verifies the JWT signature against the project's public keys.
  // Never trust getSession() here -- it reads a cookie anyone can forge.
  const { data } = await supabase.auth.getClaims();

  const isPublicRoute = PUBLIC_PREFIXES.some((prefix) =>
    request.nextUrl.pathname.startsWith(prefix),
  );

  if (!data?.claims && !isPublicRoute) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  return supabaseResponse;
}
