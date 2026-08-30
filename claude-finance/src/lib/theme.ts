export const THEME_STORAGE_KEY = "fintrack-theme";

export const THEME_MODES = ["system", "light", "dark"] as const;

export type ThemeMode = (typeof THEME_MODES)[number];

export const DEFAULT_THEME_MODE: ThemeMode = "system";

export const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

export function isThemeMode(value: unknown): value is ThemeMode {
  return THEME_MODES.includes(value as ThemeMode);
}

/** Client-only. `localStorage` throws in some privacy modes, hence the catch. */
export function readThemeMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeMode(stored) ? stored : DEFAULT_THEME_MODE;
  } catch {
    return DEFAULT_THEME_MODE;
  }
}

export function nextThemeMode(mode: ThemeMode): ThemeMode {
  return THEME_MODES[(THEME_MODES.indexOf(mode) + 1) % THEME_MODES.length];
}

/**
 * The single writer of the two theme signals on `<html>`: the `dark` class the
 * Tailwind variant and the `.dark` palette key off, and `data-theme-mode`,
 * which records the *stored* choice so the toggle can render the right icon
 * from CSS alone. Kept in sync with the inline script in `theme-script.tsx`.
 */
export function applyThemeMode(mode: ThemeMode): void {
  const root = document.documentElement;
  root.classList.toggle(
    "dark",
    mode === "dark" ||
      (mode === "system" && window.matchMedia(DARK_MEDIA_QUERY).matches)
  );
  root.dataset.themeMode = mode;
}

export function storeThemeMode(mode: ThemeMode): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    // A rejected write only costs the preference its persistence.
  }
}
