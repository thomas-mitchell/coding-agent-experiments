"use client";

import { useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Plus } from "lucide-react";

import { addOrUpdatePosition } from "@/actions/portfolio-actions";
import {
  StockPositionFormSchema,
  type StockPositionFormValues,
} from "@/lib/schemas";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";

export function StockForm() {
  const [isPending, startTransition] = useTransition();
  const [serverError, setServerError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const form = useForm<StockPositionFormValues>({
    resolver: zodResolver(StockPositionFormSchema),
    defaultValues: { ticker: "", shares: "" },
  });

  function onSubmit(values: StockPositionFormValues) {
    setServerError(null);
    const symbol = values.ticker.trim().toUpperCase();

    startTransition(async () => {
      const result = await addOrUpdatePosition(symbol, Number(values.shares));

      if (!result.ok) {
        setServerError(result.error);
        return;
      }

      form.reset({ ticker: "", shares: "" });
      setSaved(symbol);
    });
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <FieldGroup className="gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="ticker">Ticker</FieldLabel>
            <Input
              id="ticker"
              placeholder="AAPL"
              autoCapitalize="characters"
              autoComplete="off"
              spellCheck={false}
              className="uppercase"
              aria-invalid={Boolean(form.formState.errors.ticker)}
              {...form.register("ticker", {
                // Uppercase as the user types so the field always shows what
                // will actually be stored; the schema normalises it again.
                onChange: (event) => {
                  event.target.value = event.target.value.toUpperCase();
                },
              })}
            />
            <FieldError errors={[form.formState.errors.ticker]} />
          </Field>

          <Field>
            <FieldLabel htmlFor="shares">Shares</FieldLabel>
            <Input
              id="shares"
              inputMode="decimal"
              placeholder="10"
              aria-invalid={Boolean(form.formState.errors.shares)}
              {...form.register("shares")}
            />
            <FieldError errors={[form.formState.errors.shares]} />
          </Field>
        </div>

        <FieldDescription>
          Adding a ticker you already hold increases that holding — it does not
          replace it.
        </FieldDescription>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={isPending}>
            {isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-4" aria-hidden />
            )}
            {isPending ? "Adding…" : "Add position"}
          </Button>
          {serverError ? (
            <p role="alert" className="text-sm text-destructive">
              {serverError}
            </p>
          ) : saved ? (
            <p role="status" className="text-sm text-muted-foreground">
              {saved} updated.
            </p>
          ) : null}
        </div>
      </FieldGroup>
    </form>
  );
}
