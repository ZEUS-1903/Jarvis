import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api/* to FastAPI. The browser only ever talks to the Vite
    // origin, so no CORS config is needed in development.
    proxy: { "/api": "http://localhost:8000" },
  },
});
