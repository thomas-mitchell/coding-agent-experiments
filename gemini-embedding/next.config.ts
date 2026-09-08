import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["ffmpeg-static", "unpdf", "pdf-lib"],
  experimental: {
    serverActions: { bodySizeLimit: "512mb" },
  },
};

export default nextConfig;
