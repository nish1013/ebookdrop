import { expect, test } from "@playwright/test";
import { newEmail, signIn, signUpByApi } from "./identity.steps";

test("S2 AC1 Ana signs in and sees her library", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);

  await signIn(page, email);

  await expect(page).toHaveURL("/library");
  await expect(page.getByText("Your library is empty")).toBeVisible();
});

test("S2 AC2 Ana sees that the email or password is wrong", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);

  await signIn(page, email, "wrong horse battery");

  await expect(page.getByText("Email or password is wrong")).toBeVisible();
  await expect(page).toHaveURL("/sign-in");
});
