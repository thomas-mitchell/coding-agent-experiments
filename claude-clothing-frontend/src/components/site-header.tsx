"use client";

import { useState } from "react";

import {
  BagIcon,
  CloseIcon,
  HeartIcon,
  SearchIcon,
  UserIcon,
} from "@/components/icons";

const CATEGORIES = [
  "WOMEN",
  "MEN",
  "KIDS",
  "HOME & DESIGN",
  "BEAUTY",
  "FOOD & DRINKS",
  "PROMO",
  "GIFTING",
  "BRANDS",
  "STORES & RESTAURANTS",
  "EVENTS",
];

/**
 * Mocked storefront chrome. Everything here is decorative -- the links go
 * nowhere -- but the proportions carry the whole aesthetic, so the measurements
 * track the reference screenshot rather than being eyeballed.
 */
export function SiteHeader() {
  const [showPromo, setShowPromo] = useState(true);

  return (
    <header className="w-full">
      <div className="bg-promo px-6 py-2.5 text-center text-white">
        <span className="chrome-label">
          AI virtual try-on &mdash; experimental tool
        </span>
      </div>

      <div className="relative flex h-[72px] items-center justify-between px-6">
        <button
          type="button"
          className="flex items-center gap-3 text-ink transition-opacity hover:opacity-60"
        >
          <SearchIcon className="h-[18px] w-[18px]" />
          <span className="chrome-label hidden sm:inline">
            What are you looking for?
          </span>
        </button>

        {/*
          Absolutely centred rather than laid out between the two side blocks:
          the reference centres the wordmark on the viewport, and a flex centre
          would drift as the left and right groups change width.
        */}
        <p className="pointer-events-none absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-[22px] font-semibold tracking-[0.22em] sm:text-[30px]">
          VIRTUAL TRY-ON
        </p>

        <div className="flex items-center gap-5">
          <UserIcon className="hidden h-[19px] w-[19px] sm:block" />
          <HeartIcon className="hidden h-[19px] w-[19px] sm:block" />
          <BagIcon className="h-[19px] w-[19px]" />
          <span className="chrome-label hidden text-subtle md:inline">
            <span className="text-ink">EN</span> | IT
          </span>
        </div>
      </div>

      <div className="relative border-b border-hairline">
        {/*
          `justify-center-safe` (justify-content: safe center) rather than plain
          centring: once the categories outgrow a narrow viewport, centred
          content overflows equally in both directions and scrollLeft cannot go
          below 0, which strands the first few items permanently off-screen.
          Safe alignment falls back to start-alignment exactly when that would
          happen, so the whole list stays scrollable on mobile.
        */}
        <nav className="flex items-center justify-center-safe gap-x-7 gap-y-2 overflow-x-auto px-6 pb-3.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {CATEGORIES.map((category) => (
            <span
              key={category}
              className="chrome-label whitespace-nowrap text-ink transition-opacity hover:opacity-50"
            >
              {category}
            </span>
          ))}
        </nav>
        <span className="chrome-label absolute right-6 top-0 hidden rounded-full bg-gold px-4 py-2 xl:inline">
          Need some help?
        </span>
      </div>

      {showPromo && (
        <div className="relative border-b border-hairline px-12 py-3.5 text-center">
          <span className="chrome-label">
            Upload your images &amp; check your generated results
          </span>
          <button
            type="button"
            onClick={() => setShowPromo(false)}
            aria-label="Dismiss announcement"
            className="absolute right-5 top-1/2 -translate-y-1/2 text-subtle transition-colors hover:text-ink"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>
      )}
    </header>
  );
}
