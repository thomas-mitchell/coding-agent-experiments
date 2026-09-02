import { signout } from "@/app/auth/actions";

/**
 * Mocked storefront chrome. Still a server component -- the sign-out control is
 * a plain form posting to a server action, so nothing here ships JS.
 */
export function SiteHeader({ userName }: { userName?: string }) {
  return (
    <header className="relative w-full bg-promo px-6 py-2.5 text-center text-white">
      <span className="chrome-label">Kenji&rsquo;s modelling gig</span>

      {userName && (
        <div className="mt-2 flex items-center justify-center gap-4 sm:absolute sm:right-6 sm:top-1/2 sm:mt-0 sm:-translate-y-1/2">
          <span className="chrome-label text-white/70">{userName}</span>
          <form action={signout}>
            <button
              type="submit"
              className="chrome-label underline underline-offset-4 transition-opacity hover:opacity-70"
            >
              Sign out
            </button>
          </form>
        </div>
      )}
    </header>
  );
}
