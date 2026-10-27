import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  forbidOnly: !!process.env.CI,
  reporter: "list",
  use: { baseURL: "http://localhost:5173" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run --project ../api python ../api/scripts/serve_e2e.py",
      url: "http://127.0.0.1:8000/openapi.json",
      timeout: 120_000,
    },
    {
      command: "npm run build && npx vite preview --port 5173 --strictPort",
      url: "http://localhost:5173",
    },
  ],
});
