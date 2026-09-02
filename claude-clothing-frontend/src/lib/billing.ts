import "server-only";

import type { SupabaseClient } from "@supabase/supabase-js";
import type Stripe from "stripe";

import { createAdminClient } from "@/lib/supabase/admin";

/** Where a grant came from. Recorded on the payment row for debugging. */
export type GrantSource = "return" | "webhook";

export type GrantResult =
  | { granted: true; userId: string; alreadyRecorded: boolean }
  | { granted: false; reason: string };

/**
 * Has this user paid?
 *
 * Runs as the caller, so the "Users can view own entitlement" policy is what
 * scopes it -- passing someone else's id returns nothing rather than the truth.
 */
export async function hasAccess(
  supabase: SupabaseClient,
  userId: string,
): Promise<boolean> {
  const { data, error } = await supabase
    .from("entitlements")
    .select("has_access")
    .eq("user_id", userId)
    .maybeSingle();

  // Fail closed: a database hiccup should show the paywall, not hand out the
  // studio for free.
  if (error) {
    console.error("[billing] entitlement lookup failed", error);
    return false;
  }

  return data?.has_access === true;
}

/**
 * Records a paid Checkout Session and unlocks the user.
 *
 * Both the return route and the webhook call this, and Stripe retries webhooks,
 * so it has to be safe to run repeatedly for one session: the insert leans on
 * the unique constraint on `stripe_checkout_session_id` and ignores conflicts.
 *
 * The link between a Stripe payment and a Supabase user is
 * `client_reference_id`, which /paywall appends to the payment link URL. No id,
 * no grant -- there would be nobody to grant it to.
 */
export async function grantAccessFromSession(
  session: Stripe.Checkout.Session,
  source: GrantSource,
): Promise<GrantResult> {
  const userId = session.client_reference_id;
  if (!userId) {
    return { granted: false, reason: "session has no client_reference_id" };
  }
  if (session.payment_status !== "paid") {
    return {
      granted: false,
      reason: `payment_status is ${session.payment_status}`,
    };
  }

  const admin = createAdminClient();

  const { data: inserted, error: insertError } = await admin
    .from("payments")
    .upsert(
      {
        user_id: userId,
        stripe_checkout_session_id: session.id,
        stripe_payment_intent_id: idOf(session.payment_intent),
        stripe_customer_id: idOf(session.customer),
        customer_email:
          session.customer_details?.email ?? session.customer_email ?? null,
        amount_total: session.amount_total,
        currency: session.currency,
        payment_status: session.payment_status,
        source,
        raw: session as unknown as Record<string, unknown>,
      },
      { onConflict: "stripe_checkout_session_id", ignoreDuplicates: true },
    )
    .select("id");

  if (insertError) {
    throw new Error(`Could not record the payment: ${insertError.message}`);
  }

  // `ignoreDuplicates` returns no rows when the session was already recorded --
  // that is the second delivery of the same event, not a failure.
  const alreadyRecorded = (inserted?.length ?? 0) === 0;

  const { error: entitlementError } = await admin.from("entitlements").upsert(
    {
      user_id: userId,
      has_access: true,
      granted_at: new Date().toISOString(),
      stripe_customer_id: idOf(session.customer),
      stripe_checkout_session_id: session.id,
      updated_at: new Date().toISOString(),
    },
    { onConflict: "user_id" },
  );

  if (entitlementError) {
    throw new Error(
      `Payment recorded but access was not granted: ${entitlementError.message}`,
    );
  }

  return { granted: true, userId, alreadyRecorded };
}

/** Stripe hands back either a bare id or an expanded object. */
function idOf(value: string | { id: string } | null | undefined): string | null {
  if (!value) return null;
  return typeof value === "string" ? value : value.id;
}
