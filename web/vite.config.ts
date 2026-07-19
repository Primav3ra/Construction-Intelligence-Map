import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" -> relative asset paths so the build works on any static host
// (Vercel/Netlify/GitHub Pages subpath) without extra config.
export default defineConfig({
  plugins: [react()],
  base: "./",
});
