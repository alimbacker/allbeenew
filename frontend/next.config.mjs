/** @type {import('next').NextConfig} */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Proxy /api to FastAPI in development so the browser sees one origin.
  // This keeps cookies, CORS and Server-Sent Events simple. In production
  // Nginx does the same thing (see docs/DEPLOYMENT.md).
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
