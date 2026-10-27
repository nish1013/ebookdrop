import { makeBook } from "foliate-js/view.js";
import { BOOK_POLICY, SECTION_TYPES } from "./reader.constants";
import type { FoliateView, Pages, SectionData } from "./reader.types";

const XHTML = "http://www.w3.org/1999/xhtml";

export async function openEpub(file: Blob, container: HTMLElement): Promise<Pages> {
  const book = await makeBook(new File([file], "book.epub", { type: file.type }));
  book.transformTarget?.addEventListener("data", addBookPolicy);
  const view = document.createElement("foliate-view") as FoliateView;
  container.append(view);
  await view.open(book);
  await view.next();
  return { previous: () => view.prev(), next: () => view.next() };
}

// foliate-js needs `allow-scripts` on its section frames, so this policy is what
// stops a book script. A section that does not parse is dropped, never shown bare.
function addBookPolicy(event: Event): void {
  const detail = (event as CustomEvent<SectionData>).detail;
  if (!SECTION_TYPES.has(detail.type)) return;
  detail.data = Promise.resolve(detail.data).then((data) =>
    typeof data === "string" ? withBookPolicy(data, detail.type) : "",
  );
}

function withBookPolicy(markup: string, type: string): string {
  const doc = new DOMParser().parseFromString(markup, type as DOMParserSupportedType);
  const root = doc.documentElement;
  if (!root || doc.querySelector("parsererror")) return "";
  const head = doc.head ?? root.querySelector("head") ?? doc.createElementNS(XHTML, "head");
  root.prepend(head);
  const policy = doc.createElementNS(XHTML, "meta");
  policy.setAttribute("http-equiv", "Content-Security-Policy");
  policy.setAttribute("content", BOOK_POLICY);
  head.prepend(policy);
  return new XMLSerializer().serializeToString(doc);
}
