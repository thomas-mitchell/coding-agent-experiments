import { NextResponse, type NextRequest } from "next/server";
import type Stripe from "stripe";

import { grantAccessFromSession } from "@/lib/billing";
import { stripe, webhookSecret } from "@/lib/stripe";

/**
 * Stripe's side of the grant, and the one that survives a closed tab.
 *
 * This route is deliberately outside the auth gate (see PUBLIC_PREFIXES in
 * src/lib/supabase/proxy.ts) -- Stripe sends no cookies. The signature check
 * below is what stands in for authentication, so it is not optional.
 */
export async function POST(request: NextRequest) {
  const signature = request.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "missing signature" }, { status: 400 });
  }

  // Must be the raw body. `request.json()` re-serialises and the signature,
  // computed over the exact bytes Stripe sent, then never matches.
  const payload = await request.text();

  let event: Stripe.Event;
  try {
    event = await stripe().webhooks.constructEventAsync(
      payload,
      signature,
      webhookSecret(),
    );
  } catch (caught) {
    console.error("[stripe/webhook] signature rejected", caught);
    return NextResponse.json({ error: "invalid signature" }, { status: 400 });
  }

  if (
    event.type === "checkout.session.completed" ||
    event.type === "checkout.session.async_payment_succeeded"
  ) {
    try {
      const result = await grantAccessFromSession(
        event.data.object as Stripe.Checkout.Session,
        "webhook",
      );
      console.log(`[stripe/webhook] ${event.type}`, result);
    } catch (caught) {
      // A 500 makes Stripe retry, which is what we want for a transient
      // database failure -- the grant is idempotent, so a replay is harmless.
      console.error("[stripe/webhook] grant failed", caught);
      return NextResponse.json({ error: "grant failed" }, { status: 500 });
    }
  }

  // 200 on everything else so Stripe stops redelivering events we ignore.
  return NextResponse.json({ received: true });
}
