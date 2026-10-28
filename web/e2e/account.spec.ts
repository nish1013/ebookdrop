import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { epub } from "./books";
import { PASSWORD, newEmail, signIn, signUpByApi } from "./identity.steps";

const DUNE = epub("dune.epub", "dune.epub", { title: "Dune" });
const DUNE_ITEM = /dune/i;

async function uploadDune(page: Page): Promise<void> {
  await page.getByLabel("Book file").setInputFiles(DUNE);
  await page.getByRole("button", { name: "Upload" }).click();
}

test("S12 AC1 Ana deletes her account after an in-page confirm and cannot sign in", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);
  await uploadDune(page);
  await expect(page.getByRole("listitem").filter({ hasText: DUNE_ITEM })).toBeVisible();

  await page.getByRole("link", { name: "Account" }).click();
  await expect(page).toHaveURL("/account");
  await expect(page.getByText(email)).toBeVisible();
  await page.getByRole("button", { name: "Delete account" }).click();
  const confirm = page.getByRole("group", { name: "Delete your account?" });
  await confirm.getByRole("button", { name: "Keep" }).click();
  await expect(confirm).toBeHidden();
  await page.getByRole("button", { name: "Delete account" }).click();
  await confirm.getByRole("button", { name: "Delete for good" }).click();

  await expect(page).toHaveURL("/sign-up");
  await signIn(page, email);
  await expect(page.getByText("Email or password is wrong")).toBeVisible();
});

test("S12 AC2 Ana signs up again with the same email and sees an empty library", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);
  await uploadDune(page);
  await expect(page.getByRole("listitem").filter({ hasText: DUNE_ITEM })).toBeVisible();
  await page.goto("/account");
  await page.getByRole("button", { name: "Delete account" }).click();
  await page.getByRole("button", { name: "Delete for good" }).click();
  await expect(page).toHaveURL("/sign-up");

  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign up" }).click();

  await expect(page).toHaveURL("/library");
  await expect(page.getByText("Your library is empty")).toBeVisible();
});
