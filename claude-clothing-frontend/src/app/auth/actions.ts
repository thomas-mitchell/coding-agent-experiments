"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

/**
 * Shape returned to `useActionState`. `undefined` means "nothing submitted
 * yet"; a successful submit never returns -- it redirects instead.
 *
 * React resets an uncontrolled form once its action settles, so the values the
 * user typed come back with the error and get re-seeded as defaults. Passwords
 * are deliberately not echoed.
 */
export type AuthState =
  | { error: string; name?: string; email?: string }
  | undefined;

const MIN_PASSWORD_LENGTH = 8;
const MIN_NAME_LENGTH = 2;

export async function signup(
  _state: AuthState,
  formData: FormData,
): Promise<AuthState> {
  const name = String(formData.get("name") ?? "").trim();
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  const typed = { name, email };

  if (name.length < MIN_NAME_LENGTH) {
    return { ...typed, error: "Please enter your name." };
  }
  if (!email) {
    return { ...typed, error: "Please enter your email address." };
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    return {
      ...typed,
      error: `Your password needs at least ${MIN_PASSWORD_LENGTH} characters.`,
    };
  }

  const supabase = await createClient();
  // `options.data` lands in raw_user_meta_data, which the on_auth_user_created
  // trigger copies into public.profiles.
  const { error } = await supabase.auth.signUp({
    email,
    password,
    options: { data: { name } },
  });

  if (error) {
    return { ...typed, error: error.message };
  }

  revalidatePath("/", "layout");
  // redirect() signals by throwing, so it must sit outside any try/catch.
  redirect("/");
}

export async function login(
  _state: AuthState,
  formData: FormData,
): Promise<AuthState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (!email || !password) {
    return { email, error: "Enter your email and password." };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) {
    return { email, error: error.message };
  }

  revalidatePath("/", "layout");
  redirect("/");
}

export async function signout() {
  const supabase = await createClient();
  await supabase.auth.signOut();

  revalidatePath("/", "layout");
  redirect("/login");
}
