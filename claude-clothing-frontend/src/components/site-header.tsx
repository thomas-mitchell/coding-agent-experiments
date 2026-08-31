/**
 * Mocked storefront chrome, now just the promo bar. Stateless and
 * presentational, so it stays a server component -- nothing here ships JS.
 */
export function SiteHeader() {
  return (
    <header className="w-full bg-promo px-6 py-2.5 text-center text-white">
      <span className="chrome-label">Kenji&rsquo;s modelling gig</span>
    </header>
  );
}
