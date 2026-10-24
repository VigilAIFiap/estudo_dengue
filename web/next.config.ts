import type { NextConfig } from "next";

// A API Python roda separada; o navegador só conversa com o Next,
// que repassa /api/* ao servidor. Nenhuma credencial chega ao cliente.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  devIndicators: false,
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default config;
