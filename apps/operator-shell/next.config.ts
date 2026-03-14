import type { NextConfig } from "next";

const operatorApiOrigin = process.env.OPERATOR_API_ORIGIN || "http://127.0.0.1:8011";
const chatRuntimeOrigin = process.env.CHAT_RUNTIME_ORIGIN || "http://127.0.0.1:8000";

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
        source: "/chat-api/download/artifacts/:path*",
        destination: `${chatRuntimeOrigin}/download/artifacts/:path*`,
      },
      {
        source: "/chat-api/auth/:path*",
        destination: `${chatRuntimeOrigin}/auth/:path*`,
      },
      {
        source: "/operator-api/:path*",
        destination: `${operatorApiOrigin}/api/operator/:path*`,
      },
      {
        source: "/chat-api/:path*",
        destination: `${chatRuntimeOrigin}/api/operator/:path*`,
      },
    ];
  },
};

export default nextConfig;
