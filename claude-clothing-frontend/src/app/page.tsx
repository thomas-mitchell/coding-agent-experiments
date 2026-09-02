import { SiteHeader } from "@/components/site-header";
import { TryOnStudio } from "@/components/try-on-studio";
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

  return (
    <>
      <SiteHeader userName={userName} />
      <TryOnStudio />
    </>
  );
}
