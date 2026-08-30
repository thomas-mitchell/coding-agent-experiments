"use client";

import { useState, useTransition } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Plus } from "lucide-react";

import { addTransaction } from "@/actions/transaction-actions";
import {
  TransactionFormSchema,
  TRANSACTION_TYPES,
  categoriesFor,
  toISODateString,
  type TransactionFormValues,
  type TransactionType,
} from "@/lib/schemas";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const TYPE_LABELS: Record<TransactionType, string> = {
  INCOME: "Income",
  EXPENSE: "Expense",
};

function emptyValues(): TransactionFormValues {
  return {
    type: "EXPENSE",
    amount: "",
    date: toISODateString(new Date()),
    category: "",
    description: "",
  };
}

export function TransactionForm() {
  const [isPending, startTransition] = useTransition();
  const [serverError, setServerError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const form = useForm<TransactionFormValues>({
    resolver: zodResolver(TransactionFormSchema),
    defaultValues: emptyValues(),
  });

  // useWatch rather than form.watch(): watch() returns a fresh function each
  // render, which makes React Compiler bail out of memoizing this component.
  const control = form.control;
  const type = useWatch({ control, name: "type" });
  const category = useWatch({ control, name: "category" });
  const categories = categoriesFor(type);

  function onSubmit(values: TransactionFormValues) {
    setServerError(null);
    startTransition(async () => {
      const result = await addTransaction({
        ...values,
        amount: Number(values.amount),
        description: values.description?.trim() || undefined,
      });

      if (!result.ok) {
        setServerError(result.error);
        return;
      }

      // Keep the chosen type and date: entering a run of same-day expenses is
      // the common case, and retyping the date each time is pure friction.
      form.reset({ ...emptyValues(), type: values.type, date: values.date });
      setSavedAt(Date.now());
    });
  }

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <FieldGroup className="gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field>
            <FieldLabel htmlFor="type">Type</FieldLabel>
            <Select
              value={type}
              onValueChange={(value) => {
                const next = (value as TransactionType | null) ?? "EXPENSE";
                form.setValue("type", next);
                // Category lists differ per type, so a stale selection would
                // otherwise survive the switch and submit a mismatched pair.
                form.setValue("category", "", { shouldValidate: false });
              }}
            >
              <SelectTrigger id="type" className="w-full">
                {/*
                  Base UI renders the raw stored value unless given a formatter,
                  which would surface "EXPENSE" in the trigger.
                */}
                <SelectValue placeholder="Select a type">
                  {(value) => TYPE_LABELS[value as TransactionType] ?? value}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {TRANSACTION_TYPES.map((value) => (
                  <SelectItem key={value} value={value}>
                    {TYPE_LABELS[value]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FieldError errors={[form.formState.errors.type]} />
          </Field>

          <Field>
            <FieldLabel htmlFor="amount">Amount</FieldLabel>
            <Input
              id="amount"
              inputMode="decimal"
              placeholder="0.00"
              aria-invalid={Boolean(form.formState.errors.amount)}
              {...form.register("amount")}
            />
            <FieldError errors={[form.formState.errors.amount]} />
          </Field>

          <Field>
            <FieldLabel htmlFor="date">Date</FieldLabel>
            <Input
              id="date"
              type="date"
              aria-invalid={Boolean(form.formState.errors.date)}
              {...form.register("date")}
            />
            <FieldError errors={[form.formState.errors.date]} />
          </Field>

          <Field>
            <FieldLabel htmlFor="category">Category</FieldLabel>
            <Select
              value={category || null}
              onValueChange={(value) =>
                form.setValue("category", (value as string | null) ?? "", {
                  shouldValidate: true,
                })
              }
            >
              <SelectTrigger id="category" className="w-full">
                <SelectValue placeholder="Select a category" />
              </SelectTrigger>
              <SelectContent>
                {categories.map((category) => (
                  <SelectItem key={category} value={category}>
                    {category}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <FieldError errors={[form.formState.errors.category]} />
          </Field>
        </div>

        <Field>
          <FieldLabel htmlFor="description">Description (optional)</FieldLabel>
          <Input
            id="description"
            placeholder="Weekly shop, rent, paycheck…"
            aria-invalid={Boolean(form.formState.errors.description)}
            {...form.register("description")}
          />
          <FieldError errors={[form.formState.errors.description]} />
        </Field>

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={isPending}>
            {isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-4" aria-hidden />
            )}
            {isPending ? "Adding…" : "Add transaction"}
          </Button>
          {serverError ? (
            <p role="alert" className="text-sm text-destructive">
              {serverError}
            </p>
          ) : savedAt ? (
            <p role="status" className="text-sm text-muted-foreground">
              Transaction added.
            </p>
          ) : null}
        </div>
      </FieldGroup>
    </form>
  );
}
