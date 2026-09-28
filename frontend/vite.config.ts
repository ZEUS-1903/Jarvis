import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Pre-bundle React when the dev server starts instead of discovering it on the
  // first page load. Avoids a first-load race where the browser gets two React
  // copies and renders a blank page until refresh.
  optimizeDeps: {
    include: ["react", "react-dom", "react-dom/client", "react/jsx-dev-runtime"],
  },
  server: {
    // Forward /api/* to FastAPI. The browser only ever talks to the Vite
    // origin, so no CORS config is needed in development.
    proxy: { "/api": "http://localhost:8000" },
  },
});
