import { redirect } from "next/navigation";

import { SiteHeader } from "@/components/site-header";
import { TryOnStudio } from "@/components/try-on-studio";
import { hasAccess } from "@/lib/billing";
import { createClient } from "@/lib/supabase/server";

// Reading the signed-in user makes this route dynamic rather than prerendered,
// which is the point: the page is now per-user. The proxy has already turned
// signed-out visitors away, so there is always a user here.
export default async function Home() {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();

  const claims = data?.claims;
  const metadata = claims?.user_metadata as { name?: string } | undefined;
  const userName = metadata?.name?.trim() || (claims?.email as string | undefined);

  // The studio is paid. Note this gate only hides the UI: try-on.ts still posts
  // to the n8n webhook straight from the browser, and that URL is NEXT_PUBLIC_,
  // so it is bypassable by hand. Closing that means moving the call behind a
  // route handler -- see the "How the request works" section of the README.
  const userId = claims?.sub as string | undefined;
  if (!userId || !(await hasAccess(supabase, userId))) redirect("/paywall");

  return (
    <>
      <SiteHeader userName={userName} />
      <TryOnStudio />
    </>
  );
}
