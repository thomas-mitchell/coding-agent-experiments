"use client";

import Link from "next/link";
import { useActionState } from "react";

import { login, signup, type AuthState } from "@/app/auth/actions";

const FIELD_CLASS =
  "w-full border border-hairline bg-fill px-4 py-3 text-[14px] text-ink outline-none placeholder:text-subtle focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2";

const COPY = {
  login: {
    heading: "Sign in",
    blurb: "Welcome back. Sign in to get Kenji dressed.",
    submit: "Sign in",
    pending: "Signing in\u2026",
    switchText: "No account yet?",
    switchLabel: "Create one",
    switchHref: "/signup",
  },
  signup: {
    heading: "Create account",
    blurb: "Sign up with your name, email and a password.",
    submit: "Create account",
    pending: "Creating account\u2026",
    switchText: "Already have an account?",
    switchLabel: "Sign in",
    switchHref: "/login",
  },
} as const;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  // One component for both routes: the flows differ only by the name field and
  // the wording, and keeping them together keeps the two forms from drifting.
  const copy = COPY[mode];
  const [state, action, pending] = useActionState<AuthState, FormData>(
    mode === "signup" ? signup : login,
    undefined,
  );

  return (
    <main className="mx-auto w-full max-w-[420px] px-6 pb-24 pt-16">
      <h1 className="chrome-label">{copy.heading}</h1>
      <p className="mt-4 text-[15px] leading-relaxed text-subtle">
        {copy.blurb}
      </p>

      {state?.error && (
        <p
          role="alert"
          className="mt-6 border border-hairline border-l-2 border-l-ink bg-fill px-4 py-3 text-[12px] leading-relaxed text-ink"
        >
          {state.error}
        </p>
      )}

      <form action={action} className="mt-6 flex flex-col gap-5">
        {mode === "signup" && (
          <div className="flex flex-col gap-2">
            <label className="chrome-label text-subtle" htmlFor="name">
              Name
            </label>
            <input
              id="name"
              name="name"
              type="text"
              autoComplete="name"
              required
              minLength={2}
              placeholder="Kenji"
              defaultValue={state?.name}
              className={FIELD_CLASS}
            />
          </div>
        )}

        <div className="flex flex-col gap-2">
          <label className="chrome-label text-subtle" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            placeholder="you@example.com"
            defaultValue={state?.email}
            className={FIELD_CLASS}
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="chrome-label text-subtle" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete={
              mode === "signup" ? "new-password" : "current-password"
            }
            required
            minLength={mode === "signup" ? 8 : undefined}
            className={FIELD_CLASS}
          />
          {mode === "signup" && (
            <p className="text-[12px] text-subtle">At least 8 characters.</p>
          )}
        </div>

        <button
          type="submit"
          disabled={pending}
          className="chrome-label mt-1 flex items-center justify-center gap-3 bg-ink px-8 py-4 text-white transition-opacity hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {pending ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
              {copy.pending}
            </>
          ) : (
            copy.submit
          )}
        </button>
      </form>

      <p className="mt-8 text-[13px] text-subtle">
        {copy.switchText}{" "}
        <Link href={copy.switchHref} className="text-ink underline">
          {copy.switchLabel}
        </Link>
      </p>
    </main>
  );
}
