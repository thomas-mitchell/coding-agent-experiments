import { TriangleAlert } from "lucide-react";

import {
  deletePosition,
  getPortfolioWithPrices,
} from "@/actions/portfolio-actions";
import { DeleteButton } from "@/components/delete-button";
import { StockForm } from "@/components/forms/stock-form";
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
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrency, formatShares } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function PortfolioPage() {
  const positions = await getPortfolioWithPrices();
  const totalValue = positions.reduce((sum, p) => sum + p.totalValue, 0);
  const unpricedCount = positions.filter((p) => p.priceUnavailable).length;

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Portfolio</h1>
        <p className="text-sm text-muted-foreground">
          Holdings priced live from Yahoo Finance on every page load.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Add a position</CardTitle>
          <CardDescription>
            Tickers use Yahoo&apos;s symbols — e.g. <code>AAPL</code>,{" "}
            <code>BHP.AX</code>, <code>^GSPC</code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <StockForm />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Holdings</CardTitle>
          <CardDescription>
            {positions.length === 0
              ? "No positions yet."
              : `${positions.length} position${positions.length === 1 ? "" : "s"}.`}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {positions.length === 0 ? (
            <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              Add a ticker above to start tracking its live value.
            </p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Ticker</TableHead>
                      <TableHead className="text-right">Shares</TableHead>
                      <TableHead className="text-right">Live Price</TableHead>
                      <TableHead className="text-right">Total Value</TableHead>
                      <TableHead className="w-12 text-right">
                        <span className="sr-only">Actions</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {positions.map((position) => (
                      <TableRow key={position.id}>
                        <TableCell>
                          <div className="font-medium">{position.ticker}</div>
                          {position.name ? (
                            <div className="max-w-[24ch] truncate text-xs text-muted-foreground">
                              {position.name}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">
                          {formatShares(position.shares)}
                        </TableCell>
                        <TableCell className="text-right tabular-nums whitespace-nowrap">
                          {position.priceUnavailable ? (
                            <span className="inline-flex items-center gap-1 text-muted-foreground">
                              <TriangleAlert className="size-3.5" aria-hidden />
                              Unavailable
                            </span>
                          ) : (
                            formatCurrency(position.price)
                          )}
                        </TableCell>
                        <TableCell className="text-right font-medium tabular-nums whitespace-nowrap">
                          {position.priceUnavailable
                            ? "—"
                            : formatCurrency(position.totalValue)}
                        </TableCell>
                        <TableCell className="text-right">
                          <DeleteButton
                            action={deletePosition.bind(null, position.id)}
                            label={`Delete ${position.ticker} position`}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                  <TableFooter>
                    <TableRow>
                      <TableCell colSpan={3} className="font-medium">
                        Total Portfolio Value
                      </TableCell>
                      <TableCell className="text-right text-base font-semibold tabular-nums whitespace-nowrap">
                        {formatCurrency(totalValue)}
                      </TableCell>
                      <TableCell />
                    </TableRow>
                  </TableFooter>
                </Table>
              </div>

              {unpricedCount > 0 ? (
                <p className="flex items-start gap-2 rounded-lg border border-dashed p-3 text-xs text-muted-foreground">
                  <TriangleAlert
                    className="mt-0.5 size-3.5 shrink-0"
                    aria-hidden
                  />
                  <span>
                    {unpricedCount} position
                    {unpricedCount === 1 ? "" : "s"} could not be priced — check
                    the symbol, or Yahoo may be rate limiting. Unpriced holdings
                    count as $0 in the total.
                  </span>
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
