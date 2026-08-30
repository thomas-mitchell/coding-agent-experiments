# FinTrack

Local personal-finance tracker: manual income/expense entry, a stock portfolio
priced live from Yahoo Finance, and a dashboard summarising the current month.

Next.js 16 (App Router, React Server Components) · TypeScript · Tailwind v4 ·
shadcn/ui · Prisma + SQLite · Server Actions · Recharts · yahoo-finance2.

## Getting started

```bash
npm install
npx prisma db push     # creates prisma/dev.db from schema.prisma
npm run db:seed        # optional sample data
npm run dev            # http://localhost:3000
```

| Script | What it does |
|---|---|
| `npm run dev` | Dev server (webpack — see *Environment notes*) |
| `npm run build` | Production build |
| `npm run db:push` | Sync `schema.prisma` to the SQLite file |
| `npm run db:seed` | Replace all data with the sample set |
| `npm run db:studio` | Prisma Studio |
| `npm run lint` | ESLint |

## Structure

```
src/
  app/                     layout + nav, dashboard, /transactions, /portfolio
  actions/                 server actions (transaction-actions, portfolio-actions)
  components/
    forms/                 react-hook-form + zod client forms
    charts/                recharts expense pie chart
    ui/                    shadcn/ui components
  lib/
    prisma.ts              PrismaClient singleton (HMR-safe)
    schemas.ts             zod schemas shared by forms and actions
    yahoo-finance.ts       yahoo-finance2 wrapper
    format.ts              currency/share formatting
```

Two notes on the layout:

- **zod schemas live in `lib/schemas.ts`, not in the action files.** A
  `"use server"` module may only export async functions, so the schemas cannot
  live beside the actions that use them — and the client forms need the same
  definitions.
- Each schema has a **form variant** (`TransactionFormSchema`) whose numeric
  fields are strings, matching what an `<input>` actually holds. The server
  re-validates against the canonical schema regardless of what the client sent.

## Environment notes

**This project sits on `D:`, which is exFAT.** That filesystem cannot represent
symlinks, and it changes two things:

- **`next dev` runs under webpack, not Turbopack.** Turbopack creates junction
  points under `.next/` for server-external packages (Prisma among them, whether
  or not it is listed in `next.config.ts`); exFAT rejects them with `os error 1`
  and the dev server 500s on any page that touches the database.
- **`npm run build` does not work on this drive**, under either bundler.
  Turbopack fails on the same junction creation; webpack fails because
  `readlink` on an ordinary exFAT file returns `EISDIR` rather than the `EINVAL`
  its resolver expects. The build has been verified to pass on an NTFS volume
  with both bundlers and no code changes — moving the project to `C:` (or any
  NTFS drive) restores `next build`, and lets `dev` drop back to Turbopack.

Dev, lint, and typecheck all work here; only the production build needs NTFS.

## Dependency pins

Node is v20.15.1, which constrains several packages. These pins are deliberate:

| Package | Pin | Why |
|---|---|---|
| `prisma`, `@prisma/client` | `6.19.3` | Prisma 7+ needs Node `^20.19 \|\| ^22.12 \|\| >=24`. Also, `prisma`'s npm `latest` tag is currently an **8.0.0 RC** while `@prisma/client`'s is `7.10.0`, so an unpinned install produces a mismatched pair. |
| `yahoo-finance2` | `3.15.4` | v4 hard-requires Node 22. v2 is unmaintained and its cookie/crumb flow no longer works against Yahoo. |

`yahoo-finance2` v3 declares `engines.node >= 20` but its own runtime check wants
`>= 22`, so it logs an "Unsupported environment" warning on construction. Quotes
were verified to work correctly on Node 20; `lib/yahoo-finance.ts` drops that one
log line and passes everything else through.

`npm audit` reports a high-severity advisory in `deepmerge-ts`, reached only via
`@prisma/config` — the Prisma **CLI**, not the runtime client. Fixing it means
downgrading the CLI away from the client version it must match, so it is left
as-is; it is not on any request path.

## Chart colours

The expense pie uses a categorical palette validated for colour-vision
deficiency and contrast (`--viz-1` … `--viz-8` plus `--viz-other` in
`globals.css`). Two rules matter if you change it:

- **Colour follows the category, never its rank**, so a change in the month's mix
  never repaints the surviving slices.
- **Slot order is the CVD-safety mechanism.** Slices are drawn in the canonical
  category order so the ring's adjacent pairs are the pairs that were validated.
  Do not reorder or cycle the slots.

The light-mode palette carries a sub-3:1 contrast warning on three slots, which
is why the chart ships a legend with visible values and percentages rather than
relying on the fills alone.
