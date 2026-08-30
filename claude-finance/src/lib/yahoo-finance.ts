import "server-only";

import YahooFinance from "yahoo-finance2";

export type Quote = {
  price: number;
  currency: string | null;
  name: string | null;
};

/**
 * yahoo-finance2 v3 declares `engines.node >= 20` but its own runtime check
 * demands >= 22, so on Node 20 it logs an "Unsupported environment" warning on
 * every construction. Quotes have been verified to work correctly here, so that
 * one line is dropped and every other log is passed through untouched. Pinning
 * v3 is deliberate: v4 hard-requires Node 22, and v2 is unmaintained and its
 * crumb flow no longer works against Yahoo.
 */
const UNSUPPORTED_ENV_NOTICE = "Unsupported environment";

const logger = {
  info: (...args: unknown[]) => console.info(...args),
  warn: (...args: unknown[]) => {
    if (typeof args[0] === "string" && args[0].includes(UNSUPPORTED_ENV_NOTICE)) {
      return;
    }
    console.warn(...args);
  },
  error: (...args: unknown[]) => console.error(...args),
  debug: () => {},
  dir: (...args: unknown[]) => console.dir(...args),
};

// One instance per process keeps Yahoo's cookie/crumb pair cached; rebuilding it
// per request would re-run the handshake and invite rate limiting. globalThis
// carries it across dev HMR passes for the same reason.
const globalForYahoo = globalThis as unknown as {
  yahooFinance: InstanceType<typeof YahooFinance> | undefined;
};

const yahooFinance =
  globalForYahoo.yahooFinance ??
  new YahooFinance({ suppressNotices: ["yahooSurvey", "ripHistorical"], logger });

if (process.env.NODE_ENV !== "production") {
  globalForYahoo.yahooFinance = yahooFinance;
}

/**
 * Returns `null` when the ticker cannot be priced — Yahoo answers an unknown
 * symbol with an empty result rather than an error, so both the throw and the
 * undefined-price path have to be handled.
 */
export async function getQuote(ticker: string): Promise<Quote | null> {
  try {
    const result = await yahooFinance.quote(ticker);
    const price = result?.regularMarketPrice;

    if (typeof price !== "number" || !Number.isFinite(price)) {
      return null;
    }

    return {
      price,
      currency: result?.currency ?? null,
      name: result?.shortName ?? result?.longName ?? null,
    };
  } catch (error) {
    console.error(`[yahoo-finance] quote failed for ${ticker}`, error);
    return null;
  }
}
