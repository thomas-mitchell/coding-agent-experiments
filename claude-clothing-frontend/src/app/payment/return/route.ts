import { NextResponse, type NextRequest } from "next/server";

import { grantAccessFromSession } from "@/lib/billing";
import { stripe } from "@/lib/stripe";
import { createClient } from "@/lib/supabase/server";

/**
 * Where the Stripe payment link drops the buyer once checkout clears.
 *
 * The webhook is the durable source of truth, but it can arrive after the
 * browser does -- and locally it cannot arrive at all, since Stripe will not
 * post to localhost. So this route grants access itself: it re-reads the
 * Checkout Session straight from Stripe, which is what makes the `session_id`
 * in the URL trustworthy. Anything the browser hands us is a claim, not proof.
 *
 * A route handler rather than a page because it mutates: rendering a page can
 * be retried or prefetched, and neither should quietly hand out access.
 */
export async function GET(request: NextRequest) {
  const sessionId = request.nextUrl.searchParams.get("session_id");
  if (!sessionId) return back(request, "missing_session");

  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getClaims();
    const userId = data?.claims?.sub as string | undefined;
    if (!userId) {
      // Session expired while they were paying. The webhook still grants access,
      // so signing back in picks it up.
      return NextResponse.redirect(new URL("/login", request.url));
    }

    const session = await stripe().checkout.sessions.retrieve(sessionId);

    // The signed-in user must be the one the payment was started for. Without
    // this, anyone could paste someone else's session id and inherit their
    // purchase.
    if (session.client_reference_id !== userId) return back(request, "mismatch");

    const result = await grantAccessFromSession(session, "return");
    if (!result.granted) return back(request, "unpaid");

    return NextResponse.redirect(new URL("/", request.url));
  } catch (caught) {
    console.error("[payment/return] could not confirm the checkout", caught);
    return back(request, "failed");
  }
}

function back(request: NextRequest, status: string) {
  const url = new URL("/paywall", request.url);
  url.searchParams.set("status", status);
  return NextResponse.redirect(url);
}
