"use client";

import { useEffect, useMemo } from "react";

/**
 * Returns an object URL for `source`, revoking it as soon as the source
 * changes or the component unmounts.
 *
 * The URL is derived during render rather than pushed into state from an
 * effect: that avoids the cascading extra render, and means the preview is
 * available on the very first paint instead of a frame later. Revocation is
 * keyed on the URL itself, so every value this hook hands out is cleaned up by
 * the cleanup that follows it -- without that, each re-upload would strand a
 * whole image in the tab's memory for the rest of the session.
 *
 * Object URLs are used in place of the FileReader data URLs the brief
 * sketched: same rendered result, but synchronous, and it avoids inflating a
 * multi-MB image ~33% into a base64 string parked in React state.
 */
export function useObjectUrl(source: Blob | null): string | null {
  const url = useMemo(
    () => (source ? URL.createObjectURL(source) : null),
    [source],
  );

  useEffect(() => {
    if (!url) return;
    return () => URL.revokeObjectURL(url);
  }, [url]);

  return url;
}
