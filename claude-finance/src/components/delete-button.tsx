"use client";

import { useState, useTransition } from "react";
import { Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";

type DeleteAction = () => Promise<{ ok: true } | { ok: false; error: string }>;

/**
 * Takes a server action already bound to its id, so the row stays server
 * rendered and only this button ships client JS.
 */
export function DeleteButton({
  action,
  label,
}: {
  action: DeleteAction;
  label: string;
}) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex items-center justify-end gap-2">
      {error ? (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      ) : null}
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-label={label}
        title={label}
        disabled={isPending}
        onClick={() =>
          startTransition(async () => {
            setError(null);
            const result = await action();
            if (!result.ok) setError(result.error);
          })
        }
      >
        {isPending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <Trash2 className="size-4" aria-hidden />
        )}
      </Button>
    </div>
  );
}
