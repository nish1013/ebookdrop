import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { newEmail, signIn, signUpByApi } from "./identity.steps";

const DUNE = { name: "dune.epub", mimeType: "application/epub+zip", buffer: Buffer.from("PK\u0003\u0004dune") };

async function uploadDune(page: Page): Promise<void> {
  await page.getByLabel("Book file").setInputFiles(DUNE);
  await page.getByRole("button", { name: "Upload" }).click();
}

test("S4 AC1 Ana uploads dune.epub and sees it Processing", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);

  await uploadDune(page);

  const book = page.getByRole("listitem").filter({ hasText: "dune.epub" });
  await expect(book.getByText("Processing")).toBeVisible();
});

test("S6 AC1 Ana sees the converted book Ready with its cover", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);

  await uploadDune(page);

  const book = page.getByRole("listitem").filter({ hasText: "dune.epub" });
  await expect(book.getByText("Ready")).toBeVisible({ timeout: 15_000 });
  await expect(book.getByRole("img", { name: "Cover of dune.epub" })).toBeVisible();
});
