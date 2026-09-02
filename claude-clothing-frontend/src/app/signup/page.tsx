import { redirect } from "next/navigation";

import { AuthForm } from "@/components/auth-form";
import { SiteHeader } from "@/components/site-header";
import { createClient } from "@/lib/supabase/server";

export default async function SignupPage() {
  const supabase = await createClient();
  const { data } = await supabase.auth.getClaims();
  if (data?.claims) redirect("/");

  return (
    <>
      <SiteHeader />
      <AuthForm mode="signup" />
    </>
  );
}
