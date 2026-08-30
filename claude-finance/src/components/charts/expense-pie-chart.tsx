"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { formatCurrency } from "@/lib/format";

export type ExpenseSlice = {
  category: string;
  amount: number;
};

/**
 * Colour follows the category, never its rank, so filtering or a change in the
 * month's mix never repaints the surviving slices. Slots come from the dataviz
 * palette in its validated order; slices are drawn in this same order so the
 * ring's adjacent pairs are the pairs the validator actually cleared.
 */
const CATEGORY_SLOTS: Record<string, string> = {
  Groceries: "var(--viz-1)",
  Rent: "var(--viz-2)",
  Utilities: "var(--viz-3)",
  Transport: "var(--viz-4)",
  Dining: "var(--viz-5)",
  Health: "var(--viz-6)",
  Entertainment: "var(--viz-7)",
  Shopping: "var(--viz-8)",
  Other: "var(--viz-other)",
};

const FALLBACK = "var(--viz-other)";

function colorFor(category: string): string {
  return CATEGORY_SLOTS[category] ?? FALLBACK;
}

export function ExpensePieChart({ data }: { data: ExpenseSlice[] }) {
  const total = data.reduce((sum, slice) => sum + slice.amount, 0);

  if (data.length === 0 || total <= 0) {
    return (
      <div className="flex h-[260px] items-center justify-center rounded-lg border border-dashed">
        <p className="max-w-[28ch] text-center text-sm text-muted-foreground">
          No expenses recorded this month yet. Add one and the breakdown appears
          here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
      <div className="h-[260px] w-full lg:w-1/2">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="amount"
              nameKey="category"
              innerRadius={58}
              outerRadius={100}
              // 2px of surface between fills, per the mark spec.
              paddingAngle={1.5}
              stroke="var(--card)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {data.map((slice) => (
                <Cell key={slice.category} fill={colorFor(slice.category)} />
              ))}
            </Pie>
            <Tooltip
              cursor={false}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const slice = payload[0]?.payload as ExpenseSlice | undefined;
                if (!slice) return null;
                const share = total > 0 ? (slice.amount / total) * 100 : 0;
                return (
                  <div className="rounded-lg border bg-popover px-3 py-2 text-sm shadow-md">
                    <div className="flex items-center gap-2 font-medium">
                      <span
                        aria-hidden
                        className="size-2.5 shrink-0 rounded-[2px]"
                        style={{ background: colorFor(slice.category) }}
                      />
                      {slice.category}
                    </div>
                    <div className="mt-0.5 tabular-nums text-muted-foreground">
                      {formatCurrency(slice.amount)} · {share.toFixed(1)}%
                    </div>
                  </div>
                );
              }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/*
        Legend doubles as the table view. Light mode's contrast WARN on three
        slots makes these visible values an obligation, not a nicety: identity
        and magnitude are both readable without relying on the fill colour.
      */}
      <ul className="flex w-full flex-col gap-1.5 lg:w-1/2">
        {data.map((slice) => {
          const share = total > 0 ? (slice.amount / total) * 100 : 0;
          return (
            <li
              key={slice.category}
              className="flex items-center gap-2.5 text-sm"
            >
              <span
                aria-hidden
                className="size-2.5 shrink-0 rounded-[2px]"
                style={{ background: colorFor(slice.category) }}
              />
              <span className="flex-1 truncate">{slice.category}</span>
              <span className="tabular-nums text-muted-foreground">
                {share.toFixed(1)}%
              </span>
              <span className="w-24 text-right font-medium tabular-nums">
                {formatCurrency(slice.amount)}
              </span>
            </li>
          );
        })}
        <li className="mt-1 flex items-center gap-2.5 border-t pt-2 text-sm font-medium">
          <span className="size-2.5 shrink-0" aria-hidden />
          <span className="flex-1">Total</span>
          <span className="w-24 text-right tabular-nums">
            {formatCurrency(total)}
          </span>
        </li>
      </ul>
    </div>
  );
}
