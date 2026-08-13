import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The workspace packages ship raw TypeScript rather than a build step, so
  // Next has to compile them alongside the app.
  transpilePackages: ["@aiops/ui", "@aiops/types"],

  // Fail the production build on a type error rather than shipping one.
  // (Next 16 no longer runs ESLint during `next build`; CI runs it separately.)
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
