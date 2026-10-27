import type { ReaderMessage, ReaderState } from "./reader.types";

export const BOOK_POLICY = "script-src 'none'; object-src 'none'";
export const SECTION_TYPES: ReadonlySet<string> = new Set(["application/xhtml+xml", "text/html"]);
export const PDF_SCALE = 1.5;

const STATES: ReadonlySet<string> = new Set<ReaderState>([
  "opening",
  "opened",
  "missing",
  "failed",
  "unavailable",
  "signed_out",
]);

export const READER_MESSAGES: Partial<Record<ReaderState, string>> = {
  missing: "Book not found",
  failed: "This book cannot open here",
  unavailable: "Something went wrong. Try again.",
};

export function readerUrl(bookId: string): string {
  return `/reader.html?book=${encodeURIComponent(bookId)}`;
}

export function readerState(data: unknown): ReaderState | null {
  if (typeof data !== "object" || data === null || !("state" in data)) return null;
  const { state } = data;
  return typeof state === "string" && STATES.has(state) ? (state as ReaderState) : null;
}

export function readerMessage(state: ReaderState): ReaderMessage {
  return { state };
}
