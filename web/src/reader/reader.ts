import "./reader.css";
import { api } from "../api/client";
import { openEpub } from "./epub";
import { openPdf } from "./pdf";
import { readerMessage } from "./reader.constants";
import type { Opener, Pages, ReaderState } from "./reader.types";

const OPENERS: Record<string, Opener> = {
  "application/epub+zip": openEpub,
  "application/pdf": openPdf,
};

const container = document.getElementById("book")!;
let pages: Pages | null = null;

document.getElementById("previous")!.addEventListener("click", () => pages?.previous());
document.getElementById("next")!.addEventListener("click", () => pages?.next());

open().then((state) => window.parent.postMessage(readerMessage(state), window.location.origin));

async function open(): Promise<ReaderState> {
  const bookId = new URLSearchParams(window.location.search).get("book") ?? "";
  let file: Blob | undefined;
  try {
    const { data, response } = await api.GET("/api/books/{book_id}/content", {
      params: { path: { book_id: bookId } },
      parseAs: "blob",
    });
    if (response.status === 401) return "signed_out";
    if (response.status === 404 || response.status === 422) return "missing";
    file = data;
  } catch {
    return "unavailable";
  }
  const opener = file && OPENERS[file.type];
  if (!file || !opener) return "unavailable";
  try {
    pages = await opener(file, container);
    return "opened";
  } catch {
    return "failed";
  }
}
