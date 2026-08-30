import { z } from "zod";

export const TRANSACTION_TYPES = ["INCOME", "EXPENSE"] as const;
export type TransactionType = (typeof TRANSACTION_TYPES)[number];

export const EXPENSE_CATEGORIES = [
  "Groceries",
  "Rent",
  "Utilities",
  "Transport",
  "Dining",
  "Health",
  "Entertainment",
  "Shopping",
  "Other",
] as const;

export const INCOME_CATEGORIES = [
  "Salary",
  "Freelance",
  "Investments",
  "Gifts",
  "Other",
] as const;

export function categoriesFor(type: TransactionType): readonly string[] {
  return type === "INCOME" ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Dates cross the client/server boundary as "YYYY-MM-DD" strings rather than
 * Date objects: a Date would be serialized to UTC and `new Date("2026-08-29")`
 * parses back as UTC midnight, which renders as the *previous* day anywhere
 * west of Greenwich. `localDateFromISO` rebuilds it from parts instead.
 */
export const TransactionSchema = z.object({
  type: z.enum(TRANSACTION_TYPES),
  amount: z
    .number("Enter an amount")
    .positive("Amount must be greater than zero")
    .finite("Amount must be a real number"),
  date: z
    .string()
    .regex(ISO_DATE, "Pick a date")
    .refine((value) => !Number.isNaN(localDateFromISO(value).getTime()), {
      message: "That date does not exist",
    }),
  category: z.string().trim().min(1, "Pick a category"),
  description: z
    .string()
    .trim()
    .max(200, "Keep the description under 200 characters")
    .optional(),
});

export type TransactionInput = z.infer<typeof TransactionSchema>;

/**
 * The form variant keeps `amount` as the string an <input> actually holds, so
 * react-hook-form never has to model `unknown`. The action re-validates the
 * numeric shape with `TransactionSchema` regardless of what the client sent.
 */
export const TransactionFormSchema = TransactionSchema.extend({
  amount: z
    .string()
    .trim()
    .min(1, "Enter an amount")
    .refine((value) => Number.isFinite(Number(value)), "Amount must be a number")
    .refine((value) => Number(value) > 0, "Amount must be greater than zero"),
});

export type TransactionFormValues = z.infer<typeof TransactionFormSchema>;

export const StockPositionSchema = z.object({
  ticker: z
    .string()
    .trim()
    .min(1, "Enter a ticker")
    .max(12, "Tickers are at most 12 characters")
    .regex(/^[A-Za-z0-9.\-^]+$/, "Use letters, digits, '.', '-' or '^' only")
    .transform((value) => value.toUpperCase()),
  shares: z
    .number("Enter a share count")
    .positive("Shares must be greater than zero")
    .finite("Shares must be a real number"),
});

export const StockPositionFormSchema = z.object({
  ticker: StockPositionSchema.shape.ticker,
  shares: z
    .string()
    .trim()
    .min(1, "Enter a share count")
    .refine((value) => Number.isFinite(Number(value)), "Shares must be a number")
    .refine((value) => Number(value) > 0, "Shares must be greater than zero"),
});

export type StockPositionFormValues = z.input<typeof StockPositionFormSchema>;

export function localDateFromISO(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function toISODateString(date: Date): string {
  const year = String(date.getFullYear()).padStart(4, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
