import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use default output on Vercel; keep custom output locally to avoid Windows lock contention.
  distDir: process.env.VERCEL ? ".next" : ".next-runtime",
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
