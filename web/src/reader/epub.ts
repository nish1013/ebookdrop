import { makeBook } from "foliate-js/view.js";
import { BOOK_POLICY, MARKUP_TYPES, POLICY_TYPES } from "./reader.constants";
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

// foliate-js needs `allow-scripts` on its section frames, and an SVG document has no
// place for the policy meta. So each section loses its scripts and handlers, and the
// policy stops what is left. A section that does not parse is dropped, never shown bare.
function addBookPolicy(event: Event): void {
  const detail = (event as CustomEvent<SectionData>).detail;
  if (!MARKUP_TYPES.has(detail.type)) return;
  detail.data = Promise.resolve(detail.data).then((data) =>
    typeof data === "string" ? withoutScripts(data, detail.type) : "",
  );
}

function withoutScripts(markup: string, type: string): string {
  const doc = new DOMParser().parseFromString(markup, type as DOMParserSupportedType);
  const root = doc.documentElement;
  if (!root || doc.querySelector("parsererror")) return "";
  for (const script of doc.querySelectorAll("script")) script.remove();
  for (const element of doc.querySelectorAll("*")) removeScriptAttributes(element);
  if (POLICY_TYPES.has(type)) addPolicy(doc, root);
  return new XMLSerializer().serializeToString(doc);
}

function removeScriptAttributes(element: Element): void {
  for (const { name, value } of [...element.attributes]) {
    const url = [...value].filter((char) => char > " ").join("").toLowerCase();
    if (name.toLowerCase().startsWith("on") || name === "srcdoc" || url.startsWith("javascript:")) {
      element.removeAttribute(name);
    }
  }
}

function addPolicy(doc: Document, root: Element): void {
  const head = doc.head ?? root.querySelector("head") ?? doc.createElementNS(XHTML, "head");
  root.prepend(head);
  const policy = doc.createElementNS(XHTML, "meta");
  policy.setAttribute("http-equiv", "Content-Security-Policy");
  policy.setAttribute("content", BOOK_POLICY);
  head.prepend(policy);
}
