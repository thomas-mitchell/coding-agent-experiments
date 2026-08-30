"use server";

import { revalidatePath } from "next/cache";
import type { Transaction } from "@prisma/client";

import { prisma } from "@/lib/prisma";
import {
  TransactionSchema,
  type TransactionInput,
  localDateFromISO,
} from "@/lib/schemas";

export type ActionResult = { ok: true } | { ok: false; error: string };

/**
 * Every export of a "use server" module is reachable as a POST endpoint, not
 * just through the UI, so each action re-validates its own input rather than
 * trusting that the client-side resolver already ran.
 */
export async function addTransaction(
  data: TransactionInput
): Promise<ActionResult> {
  const parsed = TransactionSchema.safeParse(data);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid transaction" };
  }

  const { type, amount, date, category, description } = parsed.data;

  try {
    await prisma.transaction.create({
      data: {
        type,
        amount,
        date: localDateFromISO(date),
        category,
        description: description?.length ? description : null,
      },
    });
  } catch (error) {
    console.error("addTransaction failed", error);
    return { ok: false, error: "Could not save the transaction. Please try again." };
  }

  revalidatePath("/transactions");
  revalidatePath("/");
  return { ok: true };
}

export async function deleteTransaction(id: string): Promise<ActionResult> {
  if (typeof id !== "string" || id.length === 0) {
    return { ok: false, error: "Missing transaction id" };
  }

  try {
    await prisma.transaction.delete({ where: { id } });
  } catch (error) {
    console.error("deleteTransaction failed", error);
    return { ok: false, error: "Could not delete the transaction. Please try again." };
  }

  revalidatePath("/transactions");
  revalidatePath("/");
  return { ok: true };
}

export async function getTransactions(): Promise<Transaction[]> {
  return prisma.transaction.findMany({ orderBy: { date: "desc" } });
}
