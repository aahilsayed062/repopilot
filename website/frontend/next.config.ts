import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Avoid Windows lock/contention issues on the default ".next" directory.
  distDir: ".next-runtime",
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
