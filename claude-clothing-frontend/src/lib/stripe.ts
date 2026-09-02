import "server-only";

import Stripe from "stripe";

/** A$9.99, one-off. `PRICE_CENTS` is what the webhook payload should carry. */
export const PRICE_CENTS = 999;
export const PRICE_LABEL = "A$9.99";
export const PRICE_CURRENCY = "aud";

/*
 * Read lazily for the same reason `requireWebhookUrl()` in src/lib/try-on.ts
 * does: an unset key should surface as a readable message on the one route that
 * needs it, not as a module-evaluation crash that blanks unrelated pages.
 */
let client: Stripe | null = null;

export function stripe(): Stripe {
  if (!client) {
    const key = process.env.STRIPE_SECRET_KEY;
    if (!key) {
      throw new Error(
        "STRIPE_SECRET_KEY is not set. Copy the sandbox secret key into .env and restart the dev server.",
      );
    }
    client = new Stripe(key);
  }
  return client;
}

export function webhookSecret(): string {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) {
    throw new Error("STRIPE_WEBHOOK_SECRET is not set.");
  }
  return secret;
}

/**
 * The per-user checkout URL.
 *
 * The Payment Link itself is static -- one link for everyone. What ties a
 * payment back to an account is `client_reference_id`, which Stripe copies from
 * this query string onto the Checkout Session and into the webhook payload.
 * Without it a completed payment has no owner. `prefilled_email` is only a
 * convenience; the buyer can still change it, so it is never used as identity.
 */
export function buildPaymentLinkUrl(userId: string, email?: string): string {
  const base = process.env.NEXT_PUBLIC_STRIPE_PAYMENT_LINK_URL;
  if (!base) {
    throw new Error(
      "NEXT_PUBLIC_STRIPE_PAYMENT_LINK_URL is not set. Create a Stripe payment link and put its URL in .env.",
    );
  }

  const url = new URL(base);
  url.searchParams.set("client_reference_id", userId);
  if (email) url.searchParams.set("prefilled_email", email);
  return url.toString();
}
