import { expect, test } from "@playwright/test";
import { newEmail, signIn, signUpByApi } from "./identity.steps";

test("S3 AC1 after sign-out the library shows the sign-in page", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);
  await expect(page.getByText("Your library is empty")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL("/sign-in");

  await page.goto("/library");
  await expect(page).toHaveURL("/sign-in");
});
