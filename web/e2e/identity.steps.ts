import { randomUUID } from "node:crypto";
import type { APIRequestContext, Page } from "@playwright/test";

export const PASSWORD = "correct horse battery";

export function newEmail(): string {
  return `ana-${randomUUID()}@example.com`;
}

export async function signUpByApi(request: APIRequestContext, email: string): Promise<void> {
  const response = await request.post("/api/accounts", { data: { email, password: PASSWORD } });
  if (response.status() !== 201) throw new Error(`sign-up answered ${response.status()}`);
}

export async function signIn(page: Page, email: string, password = PASSWORD): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}
