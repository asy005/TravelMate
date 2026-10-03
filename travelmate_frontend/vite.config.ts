import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      server: {
        host: true,
        strictPort: false,
        port: 5173,
      },      
    },
  },
  server: {
    port: 5173,
  },
});
