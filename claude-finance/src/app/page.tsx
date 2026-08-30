import { endOfMonth, format, startOfMonth } from "date-fns";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Briefcase,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { getPortfolioWithPrices } from "@/actions/portfolio-actions";
import {
  ExpensePieChart,
  type ExpenseSlice,
} from "@/components/charts/expense-pie-chart";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { formatCurrency, formatSignedCurrency } from "@/lib/format";
import { prisma } from "@/lib/prisma";
import { EXPENSE_CATEGORIES } from "@/lib/schemas";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** Canonical order keeps pie adjacency equal to the validated palette order. */
const CATEGORY_ORDER: ReadonlyMap<string, number> = new Map(
  EXPENSE_CATEGORIES.map((category, index) => [category as string, index])
);

async function getMonthSummary(monthStart: Date, monthEnd: Date) {
  const range = { date: { gte: monthStart, lte: monthEnd } };

  // Aggregated in SQLite rather than summed in JS: the dashboard should not
  // pull every row just to total it.
  const [income, expenses, byCategory] = await Promise.all([
    prisma.transaction.aggregate({
      where: { ...range, type: "INCOME" },
      _sum: { amount: true },
    }),
    prisma.transaction.aggregate({
      where: { ...range, type: "EXPENSE" },
      _sum: { amount: true },
    }),
    prisma.transaction.groupBy({
      by: ["category"],
      where: { ...range, type: "EXPENSE" },
      _sum: { amount: true },
    }),
  ]);

  const slices: ExpenseSlice[] = byCategory
    .map((row) => ({
      category: row.category,
      amount: row._sum.amount ?? 0,
    }))
    .filter((slice) => slice.amount > 0)
    .sort(
      (a, b) =>
        (CATEGORY_ORDER.get(a.category) ?? Number.MAX_SAFE_INTEGER) -
          (CATEGORY_ORDER.get(b.category) ?? Number.MAX_SAFE_INTEGER) ||
        a.category.localeCompare(b.category)
    );

  return {
    income: income._sum.amount ?? 0,
    expenses: expenses._sum.amount ?? 0,
    slices,
  };
}

export default async function DashboardPage() {
  const now = new Date();
  const monthStart = startOfMonth(now);
  const monthEnd = endOfMonth(now);

  const [summary, positions] = await Promise.all([
    getMonthSummary(monthStart, monthEnd),
    getPortfolioWithPrices(),
  ]);

  const portfolioValue = positions.reduce((sum, p) => sum + p.totalValue, 0);
  const netCashFlow = summary.income - summary.expenses;
  const monthLabel = format(now, "MMMM yyyy");
  const unpricedCount = positions.filter((p) => p.priceUnavailable).length;

  const cards = [
    {
      label: "Total Portfolio Value",
      value: formatCurrency(portfolioValue),
      icon: Briefcase,
      hint:
        positions.length === 0
          ? "No positions yet"
          : unpricedCount > 0
            ? `${positions.length} position${positions.length === 1 ? "" : "s"} · ${unpricedCount} unpriced`
            : `${positions.length} position${positions.length === 1 ? "" : "s"}, live`,
      tone: "neutral" as const,
    },
    {
      label: "Income",
      value: formatCurrency(summary.income),
      icon: ArrowUpRight,
      hint: monthLabel,
      tone: "positive" as const,
    },
    {
      label: "Expenses",
      value: formatCurrency(summary.expenses),
      icon: ArrowDownLeft,
      hint: monthLabel,
      tone: "neutral" as const,
    },
    {
      label: "Net Cash Flow",
      value: formatSignedCurrency(netCashFlow),
      icon: netCashFlow >= 0 ? TrendingUp : TrendingDown,
      hint: monthLabel,
      // Exactly zero is neither a win nor a loss, so it stays neutral ink.
      tone:
        netCashFlow > 0
          ? ("positive" as const)
          : netCashFlow < 0
            ? ("negative" as const)
            : ("neutral" as const),
    },
  ];

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Portfolio value is live; cash flow covers {monthLabel}.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map(({ label, value, icon: Icon, hint, tone }) => (
          <Card key={label}>
            <CardHeader>
              <CardDescription className="flex items-center gap-1.5">
                <Icon
                  className={cn(
                    "size-3.5",
                    tone === "positive" && "text-emerald-600 dark:text-emerald-400",
                    tone === "negative" && "text-rose-600 dark:text-rose-400"
                  )}
                  aria-hidden
                />
                {label}
              </CardDescription>
              <CardTitle
                className={cn(
                  "text-2xl tabular-nums",
                  tone === "positive" && "text-emerald-700 dark:text-emerald-400",
                  tone === "negative" && "text-rose-700 dark:text-rose-400"
                )}
              >
                {value}
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-xs text-muted-foreground">{hint}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Expenses by category</CardTitle>
          <CardDescription>{monthLabel}</CardDescription>
        </CardHeader>
        <CardContent>
          <ExpensePieChart data={summary.slices} />
        </CardContent>
      </Card>
    </div>
  );
}
