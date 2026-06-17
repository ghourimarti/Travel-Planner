/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server (.next/standalone/server.js) so the runtime
  // Docker image carries only the traced node_modules, not the whole tree (P6.1).
  output: "standalone",
  // The browser never calls the FastAPI backend directly — it goes through our
  // BFF route handlers (so Auth0 access tokens stay server-side). BACKEND_API_URL
  // is read at request time in src/lib/api.ts.
  env: {
    NEXT_PUBLIC_APP_NAME: "Voyantra",
  },
};

export default nextConfig;
