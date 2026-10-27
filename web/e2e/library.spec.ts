import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import type { BookFile } from "./books";
import { epub } from "./books";
import { newEmail, signIn, signUpByApi } from "./identity.steps";

const DUNE = epub("dune.epub");

async function uploadFile(page: Page, file: BookFile): Promise<void> {
  await page.getByLabel("Book file").setInputFiles(file);
  await page.getByRole("button", { name: "Upload" }).click();
}

async function uploadDune(page: Page): Promise<void> {
  await uploadFile(page, DUNE);
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

test("S4 AC6 Ana uploads the same bytes again and gets a link to dune.epub", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);
  await uploadDune(page);
  await expect(page.getByRole("listitem").filter({ hasText: "dune.epub" })).toBeVisible();

  await uploadFile(page, { ...DUNE, name: "dune-copy.epub" });

  const refusal = page.getByRole("alert");
  await expect(refusal).toContainText("This book is already in your library");
  await refusal.getByRole("link", { name: "dune.epub" }).click();
  await expect(page.locator("li:target")).toContainText("dune.epub");
});
