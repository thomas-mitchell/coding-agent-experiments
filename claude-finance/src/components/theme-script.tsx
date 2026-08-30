import {
  DARK_MEDIA_QUERY,
  DEFAULT_THEME_MODE,
  THEME_STORAGE_KEY,
} from "@/lib/theme";

/**
 * Runs synchronously while the browser parses `<head>`, so the stored theme is
 * on `<html>` before the first paint — no flash of the light palette, and no
 * hydration error, because `<html>` carries `suppressHydrationWarning`.
 *
 * This is the one place the logic in `applyThemeMode` is duplicated: the script
 * has to be a self-contained string in the HTML, so it cannot import it.
 */
const script = `(function(){try{var m=localStorage.getItem(${JSON.stringify(
  THEME_STORAGE_KEY
)});if(m!=="light"&&m!=="dark"&&m!=="system")m=${JSON.stringify(
  DEFAULT_THEME_MODE
)};var d=m==="dark"||(m==="system"&&window.matchMedia(${JSON.stringify(
  DARK_MEDIA_QUERY
)}).matches);var r=document.documentElement;r.classList.toggle("dark",d);r.dataset.themeMode=m}catch(e){}})()`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: script }} />;
}
