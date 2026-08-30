import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

/** Day `day` of the current month, at local midnight. */
function thisMonth(day: number): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), day);
}

/** Day `day` of the previous month, so the dashboard's month filter is exercised. */
function lastMonth(day: number): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth() - 1, day);
}

const transactions = [
  { type: "INCOME", amount: 5400, date: thisMonth(1), category: "Salary", description: "Monthly salary" },
  { type: "INCOME", amount: 820, date: thisMonth(12), category: "Freelance", description: "Design retainer" },
  { type: "INCOME", amount: 145.32, date: thisMonth(18), category: "Investments", description: "Dividend payout" },

  { type: "EXPENSE", amount: 1850, date: thisMonth(2), category: "Rent", description: "Apartment rent" },
  { type: "EXPENSE", amount: 214.55, date: thisMonth(3), category: "Groceries", description: "Weekly shop" },
  { type: "EXPENSE", amount: 189.2, date: thisMonth(10), category: "Groceries", description: "Weekly shop" },
  { type: "EXPENSE", amount: 176.4, date: thisMonth(17), category: "Groceries", description: "Weekly shop" },
  { type: "EXPENSE", amount: 243.18, date: thisMonth(5), category: "Utilities", description: "Electricity and gas" },
  { type: "EXPENSE", amount: 68.9, date: thisMonth(6), category: "Utilities", description: "Internet" },
  { type: "EXPENSE", amount: 132.75, date: thisMonth(8), category: "Transport", description: "Fuel and tolls" },
  { type: "EXPENSE", amount: 94.5, date: thisMonth(14), category: "Dining", description: "Dinner out" },
  { type: "EXPENSE", amount: 47.8, date: thisMonth(20), category: "Dining", description: "Team lunch" },
  { type: "EXPENSE", amount: 120, date: thisMonth(9), category: "Health", description: "Physio session" },
  { type: "EXPENSE", amount: 19.99, date: thisMonth(11), category: "Entertainment", description: "Streaming" },
  { type: "EXPENSE", amount: 310.4, date: thisMonth(15), category: "Shopping", description: "Winter jacket" },
  { type: "EXPENSE", amount: 62.3, date: thisMonth(21), category: "Other", description: "Gift" },

  { type: "INCOME", amount: 5400, date: lastMonth(1), category: "Salary", description: "Monthly salary" },
  { type: "EXPENSE", amount: 1850, date: lastMonth(2), category: "Rent", description: "Apartment rent" },
  { type: "EXPENSE", amount: 640.15, date: lastMonth(12), category: "Groceries", description: "Monthly groceries" },
];

const positions = [
  { ticker: "AAPL", shares: 12 },
  { ticker: "MSFT", shares: 5 },
  { ticker: "VOO", shares: 8.25 },
  { ticker: "NVDA", shares: 3 },
];

async function main() {
  // Idempotent: re-running replaces the sample set rather than stacking on it.
  await prisma.transaction.deleteMany();
  await prisma.stockPosition.deleteMany();

  await prisma.transaction.createMany({ data: transactions });
  await prisma.stockPosition.createMany({ data: positions });

  console.log(
    `Seeded ${transactions.length} transactions and ${positions.length} positions.`
  );
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
