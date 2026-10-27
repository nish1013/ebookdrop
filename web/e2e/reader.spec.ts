import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";
import type { BookFile } from "./books";
import { epub, pdf } from "./books";
import { newEmail, signIn, signUpByApi } from "./identity.steps";

const DUNE = epub("dune.epub", "reader-dune.epub", { title: "Dune" });
const EMMA = pdf("emma.pdf", "Emma");
const PROBE = "/probe.js";
const BOOK_POLICY = "script-src 'none'";
const HOSTILE_CHAPTER =
  "<html xmlns='http://www.w3.org/1999/xhtml'><head><title>Dune</title>" +
  "<script>localStorage.setItem('pwned', 'script')</script>" +
  `<script src='http://localhost:5173${PROBE}'></script></head>` +
  "<body><p>Dune</p><img src='missing.png' alt='' onerror=\"localStorage.setItem('pwned', 'handler')\"/></body></html>";
const HOSTILE = epub("hostile.epub", "hostile.epub", { title: "Dune", chapter: HOSTILE_CHAPTER });
const HOSTILE_SVG_PAGE =
  "<svg xmlns='http://www.w3.org/2000/svg' onload=\"localStorage.setItem('pwned', 'handler')\">" +
  "<script>localStorage.setItem('pwned', 'script')</script>" +
  `<script href='http://localhost:5173${PROBE}'/>` +
  "<text x='10' y='40'>Dune</text></svg>";
const HOSTILE_SVG = epub("hostile-svg.epub", "hostile-svg.epub", { title: "Dune", svgPage: HOSTILE_SVG_PAGE });
const READY_TIMEOUT = { timeout: 15_000 };

async function readyBook(page: Page, file: BookFile, title: RegExp): Promise<Locator> {
  await page.getByLabel("Book file").setInputFiles(file);
  await page.getByRole("button", { name: "Upload" }).click();
  const book = page.getByRole("listitem").filter({ hasText: title });
  await expect(book.getByText("Ready")).toBeVisible(READY_TIMEOUT);
  return book;
}

async function signedInReader(page: Page): Promise<void> {
  const email = newEmail();
  await signUpByApi(page.request, email);
  await signIn(page, email);
  await expect(page).toHaveURL(/\/library$/);
}

async function bookText(page: Page): Promise<string> {
  const books = page.frames().filter((frame) => frame.url().startsWith("blob:"));
  const texts = await Promise.all(books.map((frame) => frame.locator("body").innerText().catch(() => "")));
  return texts.join("\n");
}

async function svgText(page: Page): Promise<string> {
  const books = page.frames().filter((frame) => frame.url().startsWith("blob:"));
  const texts = await Promise.all(
    books.map((frame) =>
      frame
        .evaluate(() => {
          const root = document.documentElement;
          return root.localName === "svg" && document.readyState === "complete" ? root.textContent : "";
        })
        .catch(() => ""),
    ),
  );
  return texts.join("\n");
}

test("S8 AC1 Ana opens dune.epub and sees chapter 1", async ({ page }) => {
  await signedInReader(page);
  const book = await readyBook(page, DUNE, /dune/i);

  await book.getByRole("link", { name: "Read Dune" }).click();

  await expect.poll(() => bookText(page)).toContain("Dune");
});

test("S8 AC1 Ana opens emma.pdf and sees page 1", async ({ page }) => {
  await signedInReader(page);
  const book = await readyBook(page, EMMA, /emma/i);

  await book.getByRole("link", { name: /^Read / }).click();

  const reader = page.frameLocator("iframe[title='Book']");
  await expect(reader.getByRole("img", { name: "Page 1" })).toBeVisible();
});

test("S8 AC2 Ben opens Ana's book and gets the answer for a missing book", async ({ page, browser }) => {
  await signedInReader(page);
  const book = await readyBook(page, DUNE, /dune/i);
  const href = await book.getByRole("link", { name: "Read Dune" }).getAttribute("href");
  const ben = await browser.newPage();
  await signedInReader(ben);

  const answer = ben.waitForResponse((response) => response.url().endsWith("/content"));
  await ben.goto(href!);

  expect((await answer).status()).toBe(404);
  await expect(ben.getByRole("alert")).toHaveText("Book not found");
  await ben.close();
});

test("S8 AC3 Ana's browser cannot render dune.epub and the book stays Ready", async ({ page }) => {
  await signedInReader(page);
  const book = await readyBook(page, DUNE, /dune/i);
  await page.route("**/api/books/*/content", (route) =>
    route.fulfill({ body: "not a book", contentType: "application/epub+zip" }),
  );

  const report = page.waitForResponse((response) => response.url().endsWith("/open-failures"));
  await book.getByRole("link", { name: "Read Dune" }).click();

  await expect(page.getByRole("alert")).toHaveText("This book cannot open here");
  expect((await report).status()).toBe(204);
  await page.getByRole("link", { name: "Library" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: /dune/i }).getByText("Ready")).toBeVisible();
});

test("S8 AC4 Ana opens a book with a script and the script does not run", async ({ page }) => {
  const refusals: string[] = [];
  const probes: string[] = [];
  page.on("console", (message) => {
    if (message.text().includes(BOOK_POLICY)) refusals.push(message.text());
  });
  page.on("response", (response) => {
    if (response.url().endsWith(PROBE)) probes.push(response.url());
  });
  await signedInReader(page);
  const book = await readyBook(page, HOSTILE, /dune/i);

  await book.getByRole("link", { name: "Read Dune" }).click();

  await expect.poll(() => bookText(page)).toContain("Dune");
  await expect.poll(() => refusals.some((text) => text.startsWith("Executing inline event handler"))).toBe(true);
  expect(refusals.some((text) => text.startsWith("Executing inline script"))).toBe(true);
  expect(refusals.some((text) => text.startsWith("Loading the script") && text.includes(PROBE))).toBe(true);
  expect(probes).toEqual([]);
  expect(await page.evaluate(() => localStorage.getItem("pwned"))).toBeNull();
});

test("S8 AC4 Ana opens a book with a script in an SVG page and the script does not run", async ({ page }) => {
  const probes: string[] = [];
  page.on("request", (request) => {
    if (request.url().endsWith(PROBE)) probes.push(request.url());
  });
  await signedInReader(page);
  const book = await readyBook(page, DUNE, /dune/i);
  await page.route("**/api/books/*/content", (route) =>
    route.fulfill({ body: HOSTILE_SVG.buffer, contentType: HOSTILE_SVG.mimeType }),
  );

  await book.getByRole("link", { name: "Read Dune" }).click();

  await expect.poll(() => svgText(page)).toContain("Dune");
  expect(probes).toEqual([]);
  expect(await page.evaluate(() => localStorage.getItem("pwned"))).toBeNull();
});
