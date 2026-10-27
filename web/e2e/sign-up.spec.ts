import { expect, test } from "@playwright/test";
import { PASSWORD, newEmail, signUpByApi } from "./identity.steps";

test("S1 AC1 Ana signs up and sees her empty library", async ({ page }) => {
  await page.goto("/sign-up");
  await page.getByLabel("Email").fill(newEmail());
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();

  await expect(page).toHaveURL("/library");
  await expect(page.getByText("Your library is empty")).toBeVisible();
});

test("S1 AC2 Ben sees that the email already has an account", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);

  await page.goto("/sign-up");
  await page.getByLabel("Email").fill(` ${email.toUpperCase()}`);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();

  await expect(page.getByText("This email already has an account")).toBeVisible();
  await expect(page).toHaveURL("/sign-up");
});
