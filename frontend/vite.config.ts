import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5173,
    host: true,
    // Poll for file changes — filesystem events don't propagate across the
    // Windows <-> Docker (WSL2) bind mount, so HMR needs polling to work.
    watch: { usePolling: true, interval: 300 },
  },
});
