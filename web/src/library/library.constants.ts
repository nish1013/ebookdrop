import type { components } from "../api/schema";

export type BookOut = components["schemas"]["BookOut"];
export type BookStatus = BookOut["status"];
export type Failure = NonNullable<BookOut["failure"]>;

export const REFRESH_MS = 1000;

export const STATUS_LABELS: Record<BookStatus, string> = {
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

export const FAILURE_MESSAGES: Record<Failure, string> = {
  malformed: "This file is damaged",
  unreadable: "This book cannot be shown",
  timed_out: "This book took too long to convert. Upload it again.",
  crashed: "This book could not be converted",
};

export const MAX_FILE_BYTES = 50 * 1024 * 1024;
export const TOO_LARGE_MESSAGE = "Files must be 50 MB or smaller";
const FALLBACK_MESSAGE = "Something went wrong. Try again.";

const MESSAGES: Record<string, string> = {
  invalid_file_name: "This file has no usable name",
  not_epub_or_pdf: "This file is not an EPUB or PDF",
  too_large: TOO_LARGE_MESSAGE,
  drm_protected: "This file has DRM",
  password_protected: "This PDF needs a password. Remove it, then upload again.",
  damaged: "This file is damaged",
  over_quota: "Your library is full (1 GB)",
  duplicate_upload: "This book is already in your library",
};

export interface BookLink {
  id: string;
  title: string;
}

export interface Refusal {
  message: string;
  book: BookLink | null;
}

export function bookAnchor(id: string): string {
  return `book-${id}`;
}

export function refusalFor(error: object): Refusal {
  const code = "code" in error && typeof error.code === "string" ? error.code : "";
  const book =
    "book_id" in error && "title" in error && typeof error.book_id === "string" && typeof error.title === "string"
      ? { id: error.book_id, title: error.title }
      : null;
  return { message: MESSAGES[code] ?? FALLBACK_MESSAGE, book };
}
