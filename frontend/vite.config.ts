import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: frontend on :5173, backend on :8000 (proxied so the browser sees one origin).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
});
