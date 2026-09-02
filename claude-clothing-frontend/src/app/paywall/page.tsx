import { redirect } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { hasAccess } from "@/lib/billing";
import { PRICE_LABEL, buildPaymentLinkUrl } from "@/lib/stripe";
import { createClient } from "@/lib/supabase/server";

/** Messages the return route can hand back when a checkout did not stick. */
const STATUS_COPY: Record<string, string> = {
  unpaid:
    "Stripe has not marked that payment as complete. If your bank is still processing it, access unlocks as soon as Stripe confirms.",
  mismatch:
    "That payment belongs to a different account. Sign in with the email you paid under, or pay again below.",
  missing_session: "We did not get a checkout reference back from Stripe.",
  failed:
    "Something went wrong confirming your payment. It has not been lost -- try the link again, or sign out and back in.",
};

export default async function PaywallPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();

  const claims = data?.claims;
  // The proxy already turned signed-out visitors away, but claims are the only
  // thing that carries the user id and this page cannot work without one.
  if (!claims) redirect("/login");

  const userId = claims.sub as string;
  const email = claims.email as string | undefined;
  const metadata = claims.user_metadata as { name?: string } | undefined;
  const userName = metadata?.name?.trim() || email;

  // Someone who has already paid should never see a pay button.
  if (await hasAccess(supabase, userId)) redirect("/");

  const { status } = await searchParams;
  const statusMessage = status ? STATUS_COPY[status] : undefined;

  return (
    <>
      <SiteHeader userName={userName} />

      <main className="mx-auto w-full max-w-[520px] px-6 pb-24 pt-16">
        <h1 className="chrome-label">One payment, then you&rsquo;re in</h1>

        <p className="mt-4 text-[15px] leading-relaxed text-subtle">
          Your account is ready. Kenji charges a one-off {PRICE_LABEL} for the
          studio &mdash; no subscription, no per-image cost.
        </p>

        {statusMessage && (
          <p
            role="alert"
            className="mt-6 border border-hairline border-l-2 border-l-ink bg-fill px-4 py-3 text-[12px] leading-relaxed text-ink"
          >
            {statusMessage}
          </p>
        )}

        <div className="mt-8 border border-hairline bg-fill px-6 py-8">
          <p className="chrome-label text-subtle">Full access</p>
          <p className="mt-3 text-[40px] font-bold leading-none tracking-tight">
            {PRICE_LABEL}
          </p>
          <p className="mt-2 text-[13px] text-subtle">
            One-off payment, GST included. Yours for good.
          </p>

          <ul className="mt-6 flex flex-col gap-2 text-[14px] leading-relaxed">
            <li>&mdash; Unlimited try-on generations</li>
            <li>&mdash; Upload any garment, JPG, PNG or WebP</li>
            <li>&mdash; Full-resolution results, no watermark</li>
          </ul>
        </div>

        {/*
          A plain anchor, not a form: the payment link is a static Stripe URL and
          the only per-user part is the query string, so this page ships no JS.
        */}
        <a
          href={buildPaymentLinkUrl(userId, email)}
          className="chrome-label mt-8 flex items-center justify-center bg-ink px-8 py-4 text-white transition-opacity hover:opacity-85"
        >
          Pay {PRICE_LABEL} with Stripe
        </a>

        <p className="mt-6 text-[13px] leading-relaxed text-subtle">
          You will be sent to Stripe&rsquo;s checkout and brought straight back
          here once it clears. Payments are handled entirely by Stripe &mdash;
          card details never touch this site.
        </p>
      </main>
    </>
  );
}
