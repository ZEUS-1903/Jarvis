import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // Forward /api/* to FastAPI. The browser only ever talks to the Vite
    // origin, so no CORS config is needed in development.
    // ws: true also forwards WebSocket upgrades (the wake word stream).
    proxy: { "/api": { target: "http://localhost:8000", ws: true } },
  },
});
