import { defineConfig } from "vitest/config"
import react from "@vitejs/plugin-react"
import { resolve } from "path"

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    exclude: ["node_modules/**", "e2e/**", ".next/**", "dist/**"],
    coverage: { provider: "v8", reporter: ["text", "html"] },
  },
  resolve: {
    alias: { "@": resolve(__dirname, "./") },
  },
})
