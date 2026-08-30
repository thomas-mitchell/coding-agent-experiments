"use server";

import { revalidatePath } from "next/cache";

import { prisma } from "@/lib/prisma";
import { getQuote } from "@/lib/yahoo-finance";
import { StockPositionSchema } from "@/lib/schemas";

export type ActionResult = { ok: true } | { ok: false; error: string };

export type EnrichedPosition = {
  id: string;
  ticker: string;
  shares: number;
  price: number;
  totalValue: number;
  /** Distinguishes a genuine $0 quote from "Yahoo could not price this". */
  priceUnavailable: boolean;
  name: string | null;
  currency: string | null;
};

export async function addOrUpdatePosition(
  ticker: string,
  shares: number
): Promise<ActionResult> {
  const parsed = StockPositionSchema.safeParse({ ticker, shares });
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid position" };
  }

  const { ticker: symbol, shares: quantity } = parsed.data;

  try {
    // Accumulates rather than overwrites: submitting the form is "I bought
    // more", so an existing holding grows by the amount entered.
    await prisma.stockPosition.upsert({
      where: { ticker: symbol },
      update: { shares: { increment: quantity } },
      create: { ticker: symbol, shares: quantity },
    });
  } catch (error) {
    console.error("addOrUpdatePosition failed", error);
    return { ok: false, error: "Could not save the position. Please try again." };
  }

  revalidatePath("/portfolio");
  revalidatePath("/");
  return { ok: true };
}

export async function deletePosition(id: string): Promise<ActionResult> {
  if (typeof id !== "string" || id.length === 0) {
    return { ok: false, error: "Missing position id" };
  }

  try {
    await prisma.stockPosition.delete({ where: { id } });
  } catch (error) {
    console.error("deletePosition failed", error);
    return { ok: false, error: "Could not delete the position. Please try again." };
  }

  revalidatePath("/portfolio");
  revalidatePath("/");
  return { ok: true };
}

export async function getPortfolioWithPrices(): Promise<EnrichedPosition[]> {
  const positions = await prisma.stockPosition.findMany({
    orderBy: { ticker: "asc" },
  });

  if (positions.length === 0) return [];

  // allSettled, not all: one unpriceable ticker must not take down the page.
  // getQuote already swallows its own errors, so a rejection here would mean
  // something genuinely unexpected — it still degrades to price 0.
  const quotes = await Promise.allSettled(
    positions.map((position) => getQuote(position.ticker))
  );

  return positions.map((position, index) => {
    const settled = quotes[index];
    const quote = settled.status === "fulfilled" ? settled.value : null;
    const price = quote?.price ?? 0;

    return {
      id: position.id,
      ticker: position.ticker,
      shares: position.shares,
      price,
      totalValue: position.shares * price,
      priceUnavailable: quote === null,
      name: quote?.name ?? null,
      currency: quote?.currency ?? null,
    };
  });
}
