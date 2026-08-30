"use client";

import { useLayoutEffect } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DARK_MEDIA_QUERY,
  applyThemeMode,
  nextThemeMode,
  readThemeMode,
  storeThemeMode,
} from "@/lib/theme";

/**
 * Deliberately stateless: the current mode lives in `localStorage` and on
 * `<html data-theme-mode>`, and CSS picks the matching icon (see globals.css).
 * Holding it in React state instead would mean the server rendering one icon
 * and hydration rendering another — the mismatch this component exists to
 * avoid.
 */
export function ThemeToggle() {
  useLayoutEffect(() => {
    // Two jobs. In dev, React's Strict Mode remount resets the attributes the
    // inline script set on <html>, so they need re-applying; in production this
    // first call is a no-op. Then, while the mode is "system", follow the OS
    // switching underneath us.
    applyThemeMode(readThemeMode());

    const media = window.matchMedia(DARK_MEDIA_QUERY);
    const onChange = () => applyThemeMode(readThemeMode());
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  function cycle() {
    const mode = nextThemeMode(readThemeMode());
    storeThemeMode(mode);
    applyThemeMode(mode);
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      onClick={cycle}
      className="ml-auto"
    >
      <span data-mode="system">
        <Monitor aria-hidden />
        <span className="sr-only">Theme: system. Switch to light.</span>
      </span>
      <span data-mode="light">
        <Sun aria-hidden />
        <span className="sr-only">Theme: light. Switch to dark.</span>
      </span>
      <span data-mode="dark">
        <Moon aria-hidden />
        <span className="sr-only">Theme: dark. Switch to system.</span>
      </span>
    </Button>
  );
}
