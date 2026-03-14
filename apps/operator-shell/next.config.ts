import type { NextConfig } from "next";

const operatorApiOrigin = process.env.OPERATOR_API_ORIGIN || "http://127.0.0.1:8170";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  output: "standalone",
  transpilePackages: ["motion"],
  async rewrites() {
    return [
      {
        source: "/operator-api/:path*",
        destination: `${operatorApiOrigin}/api/operator/:path*`,
      },
      {
        source: "/chat-api/:path*",
        destination: `${operatorApiOrigin}/api/operator/:path*`,
      },
    ];
  },
};

export default nextConfig;
