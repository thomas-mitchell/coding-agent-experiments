import { format } from "date-fns";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";

import {
  deleteTransaction,
  getTransactions,
} from "@/actions/transaction-actions";
import { DeleteButton } from "@/components/delete-button";
import { TransactionForm } from "@/components/forms/transaction-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function TransactionsPage() {
  const transactions = await getTransactions();

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Transactions</h1>
        <p className="text-sm text-muted-foreground">
          Record income and expenses. Everything here feeds the dashboard.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add a transaction</CardTitle>
          <CardDescription>
            Amounts are always positive — the type decides the direction.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <TransactionForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
          <CardDescription>
            {transactions.length === 0
              ? "No transactions yet."
              : `${transactions.length} transaction${transactions.length === 1 ? "" : "s"}, newest first.`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {transactions.length === 0 ? (
            <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              Add your first transaction above and it will appear here.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="w-12 text-right">
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transactions.map((transaction) => {
                    const isIncome = transaction.type === "INCOME";
                    return (
                      <TableRow key={transaction.id}>
                        <TableCell className="whitespace-nowrap tabular-nums">
                          {format(transaction.date, "MMM dd, yyyy")}
                        </TableCell>
                        <TableCell>
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                              isIncome
                                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                                : "bg-rose-500/10 text-rose-700 dark:text-rose-400"
                            )}
                          >
                            {isIncome ? (
                              <ArrowUpRight className="size-3" aria-hidden />
                            ) : (
                              <ArrowDownLeft className="size-3" aria-hidden />
                            )}
                            {isIncome ? "Income" : "Expense"}
                          </span>
                        </TableCell>
                        <TableCell>{transaction.category}</TableCell>
                        <TableCell className="max-w-[22ch] truncate text-muted-foreground">
                          {transaction.description ?? "—"}
                        </TableCell>
                        <TableCell
                          className={cn(
                            "text-right font-medium tabular-nums whitespace-nowrap",
                            isIncome
                              ? "text-emerald-700 dark:text-emerald-400"
                              : "text-foreground"
                          )}
                        >
                          {isIncome ? "+" : "−"}
                          {formatCurrency(transaction.amount)}
                        </TableCell>
                        <TableCell className="text-right">
                          <DeleteButton
                            action={deleteTransaction.bind(null, transaction.id)}
                            label={`Delete ${transaction.category} transaction`}
                          />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
