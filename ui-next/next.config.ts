import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://rag-public-alb-350876191.us-west-2.elb.amazonaws.com:8000/:path*",
      },
    ];
  },
};

export default nextConfig;
