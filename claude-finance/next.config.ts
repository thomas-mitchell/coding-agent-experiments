import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Both packages reach for Node built-ins and, in Prisma's case, a generated
  // native engine. Keeping them external stops the bundler from tracing them
  // into a client chunk and surfaces boundary mistakes as build errors.
  serverExternalPackages: ["@prisma/client", "yahoo-finance2"],
};

export default nextConfig;
