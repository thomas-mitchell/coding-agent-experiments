import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
import { SiteHeader } from "@/components/site-header";
import { createClient } from "@/lib/supabase/server";

export default async function LoginPage() {
  // The proxy lets /login through unconditionally so signed-out users can reach
  // it; someone already signed in has no business seeing the form.
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (data?.claims) redirect("/");

  return (
    <>
      <SiteHeader />
      <AuthForm mode="login" />
    </>
  );
}
