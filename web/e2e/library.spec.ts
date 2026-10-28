import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import type { BookFile } from "./books";
import { epub } from "./books";
import { newEmail, signIn, signUpByApi } from "./identity.steps";

const DUNE = epub("dune.epub", "dune.epub", { title: "Dune", author: "Frank Herbert" });
const BLANK = epub("blank.epub", "blank.epub", { blank: true });
const DUNE_ITEM = /dune/i;

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

  const book = page.getByRole("listitem").filter({ hasText: DUNE_ITEM });
  await expect(book.getByText("Ready")).toBeVisible({ timeout: 15_000 });
  await expect(book.getByText("Frank Herbert")).toBeVisible();
  await expect(book.getByRole("img", { name: "Cover of Dune" })).toBeVisible();
});

test("S5 AC8 Ana uploads blank.epub and sees that the book cannot be shown", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);

  await uploadFile(page, BLANK);

  const book = page.getByRole("listitem").filter({ hasText: "blank.epub" });
  await expect(book.getByText("Failed")).toBeVisible({ timeout: 15_000 });
  await expect(book.getByText("This book cannot be shown")).toBeVisible();
});

test("S4 AC6 Ana uploads the same bytes again and gets a link to dune.epub", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);
  await uploadDune(page);
  await expect(page.getByRole("listitem").filter({ hasText: DUNE_ITEM })).toBeVisible();

  await uploadFile(page, { ...DUNE, name: "dune-copy.epub" });

  const refusal = page.getByRole("alert");
  await expect(refusal).toContainText("This book is already in your library");
  await refusal.getByRole("link", { name: DUNE_ITEM }).click();
  await expect(page.locator("li:target")).toContainText(DUNE_ITEM);
});

test("S9 AC1 Ana deletes dune.epub after an in-page confirm and it is gone from her list", async ({ page, request }) => {
  const email = newEmail();
  await signUpByApi(request, email);
  await signIn(page, email);
  await uploadDune(page);
  const book = page.getByRole("listitem").filter({ hasText: DUNE_ITEM });
  await expect(book.getByText("Ready")).toBeVisible({ timeout: 15_000 });

  await book.getByRole("button", { name: "Delete Dune" }).click();
  const confirm = book.getByRole("group", { name: "Delete Dune?" });
  await confirm.getByRole("button", { name: "Keep" }).click();
  await expect(book.getByText("Ready")).toBeVisible();
  await book.getByRole("button", { name: "Delete Dune" }).click();
  await confirm.getByRole("button", { name: "Delete for good" }).click();

  await expect(page.getByText("Your library is empty")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Your library is empty")).toBeVisible();
});
