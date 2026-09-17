import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app so Turbopack doesn't try to walk up
  // into the parent NCTIAPP folder (which has its own, unrelated lockfile).
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
