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
cp .env.example .env     # then set NEXT_PUBLIC_TRYON_WEBHOOK_URL
npm run dev              # http://localhost:3000
```

`.env` is git-ignored; `.env.example` is the committed template. Without the
variable set the page still loads, and pressing Generate reports that no
endpoint is configured.

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

Uploads are limited to JPG, PNG and WebP under 10 MB. Both the file picker and
the drop target run the same validation, since `accept` only filters the picker's
dialog and a drop bypasses it entirely.

## Deploying

Import the repository into Vercel and set the root directory to
`claude-clothing-frontend`. `npm run build` prerenders the single route as static
content, so nothing else is required.
