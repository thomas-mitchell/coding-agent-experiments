# Virtual Try-On

A single-page tool that takes a photo of a person (or mannequin) and a photo of a
garment, sends both to an n8n workflow, and renders the generated composite.

The interface is a study in the Rinascente storefront design language captured in
`docs/style-screenshot.png` -- navy promo bar, centered wordmark, wide-tracked
uppercase chrome, hairline borders, and a black action bar in place of the
reference's `FILTER BY` block. The branding is deliberately the tool's own.

## Running it

```bash
npm install
cp .env.example .env     # then fill in every value
npm run dev              # http://localhost:3000
```

`.env` is git-ignored; `.env.example` is the committed template and lists what
each value is for. Without `NEXT_PUBLIC_TRYON_WEBHOOK_URL` the page still loads
and pressing Generate reports that no endpoint is configured; without the Stripe
and Supabase secrets, `/paywall` and the payment routes are the parts that fail.

On Vercel, set `NEXT_PUBLIC_TRYON_WEBHOOK_URL` in the project's environment
variables -- `.env` is never uploaded. Because it is a `NEXT_PUBLIC_` variable it
is read at build time, so changing it needs a redeploy, not just a restart.

## How the request works

The browser posts `multipart/form-data` with fields `image1` and `image2`
**directly** to the n8n webhook -- there is no route handler in between. Two
reasons:

- A generation takes about 25 seconds. Proxying it through a Vercel function
  would hold that function open for the whole request, close to its duration
  ceiling, for no benefit.
- The webhook already sends permissive CORS headers, so the direct call needs no
  server cooperation.

The trade-off is that the webhook URL is visible in the client bundle. Moving it
into `.env` keeps it out of version control, but `NEXT_PUBLIC_` variables are
inlined at build time, so the value still ships to the browser and can be read
from devtools on the deployed site. Treat the endpoint as configuration rather
than a secret.

That is not a new exposure -- the webhook already accepts cross-origin POSTs
from any origin, so it is callable by anyone who knows the URL regardless. If it
needs to be genuinely private, two things have to change together: put the call
behind a route handler with a non-public env var (raising `maxDuration` to cover
the ~25s generation), and restrict the workflow's CORS policy at the n8n end.

The workflow responds with a raw `image/jpeg` body, which the client turns into a
Blob and renders through an object URL. `src/lib/try-on.ts` also handles a
JSON-shaped response (base64 or URL) so that changing the workflow's Respond node
surfaces a readable error instead of a silently broken image.

## Paying for it

The studio costs a one-off **A$9.99**. Signing up is free; `/` redirects to
`/paywall` until the account is paid for.

```
sign up ─► /paywall ─► Stripe payment link ─► /payment/return ─► /
                                   │
                                   └────────► /api/stripe/webhook
```

The Payment Link is a single static URL. What ties a payment to an account is
the `client_reference_id` query parameter that `/paywall` appends to it; Stripe
copies it onto the Checkout Session and into the webhook payload. Without it a
completed payment has no owner.

Access is granted twice over, deliberately:

- **`/payment/return`** is where the link drops the buyer. It re-reads the
  Checkout Session from Stripe -- which is what makes the `session_id` in the URL
  trustworthy -- checks that `client_reference_id` matches the signed-in user,
  and grants immediately. It is a route handler, not a page, because it mutates.
- **`/api/stripe/webhook`** catches everyone who closed the tab, and is the only
  path that works once the app is deployed behind a domain Stripe can reach. It
  sits outside the login gate (Stripe sends no cookies), so the signature check
  is its authentication.

Both call the same `grantAccessFromSession` in `src/lib/billing.ts`, which is
idempotent on `payments.stripe_checkout_session_id` -- Stripe retries webhooks,
and the two paths race each other on every purchase.

### What the paywall does and does not stop

It gates the *page*. It does not gate the generation: as described above, the
browser still posts straight to the n8n webhook, and that URL ships in the
bundle. Anyone willing to read devtools can still call the workflow by hand.
Closing that means the same change the previous section describes -- moving the
call behind a route handler -- with a paid check added to it.

### Tables

`entitlements` is separate from `profiles` on purpose. The `profiles` update
policy lets a user change any column on their own row, so a `has_paid` column
there would be self-grantable from the browser with the publishable key.
`entitlements` and `payments` have a select-own-row policy and **no** insert or
update policy; the only writer is the service-role key, which bypasses RLS and
never leaves the server.

| Table | Role |
| --- | --- |
| `entitlements` | One row per user, created by the signup trigger. `has_access` is the paywall |
| `payments` | One row per completed Checkout Session, `raw` keeps the whole payload |

### Going live

Everything above currently points at Stripe **test mode**. Live mode needs a new
product, price, payment link and webhook endpoint created there, the four
`.env` values swapped, and the webhook endpoint's URL pointed at the deployed
domain instead of the placeholder.

## Layout

| Path | Role |
| --- | --- |
| `src/app/layout.tsx` | Montserrat, metadata, document shell |
| `src/app/globals.css` | Palette tokens and the shared `chrome-label` type style |
| `src/components/site-header.tsx` | Mocked storefront chrome |
| `src/components/try-on-studio.tsx` | State, action bar, three-card grid |
| `src/components/upload-card.tsx` | Click / drag-and-drop upload with validation |
| `src/components/result-card.tsx` | Empty, loading and result states |
| `src/lib/try-on.ts` | Validation rules and the webhook call |
| `src/lib/use-object-url.ts` | Object-URL lifecycle for previews and the result |
| `src/app/paywall/page.tsx` | The price, and the per-user Stripe payment link |
| `src/app/payment/return/route.ts` | Verifies the Checkout Session, grants, redirects |
| `src/app/api/stripe/webhook/route.ts` | Signature check, then the same grant |
| `src/lib/billing.ts` | `hasAccess` and the idempotent `grantAccessFromSession` |
| `src/lib/stripe.ts` | Stripe client, price constants, payment-link URL builder |
| `src/lib/supabase/admin.ts` | Service-role client -- the only thing that may write billing rows |

Uploads are limited to JPG, PNG and WebP under 10 MB. Both the file picker and
the drop target run the same validation, since `accept` only filters the picker's
dialog and a drop bypasses it entirely.

## Deploying

Import the repository into Vercel and set the root directory to
`claude-clothing-frontend`, then set every variable from `.env.example` in the
project's environment settings -- `.env` is never uploaded. Note that
`NEXT_PUBLIC_` variables are read at build time, so changing one needs a
redeploy rather than a restart.

Once the domain exists, repoint the Stripe webhook endpoint at
`https://<domain>/api/stripe/webhook` and the payment link's completion redirect
at `https://<domain>/payment/return?session_id={CHECKOUT_SESSION_ID}`; both
currently hold local or placeholder URLs.
