import type { components } from "../api/schema";

export type BookOut = components["schemas"]["BookOut"];
export type BookStatus = BookOut["status"];

export const REFRESH_MS = 1000;

export const STATUS_LABELS: Record<BookStatus, string> = {
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

const MESSAGES: Record<string, string> = {
  invalid_file_name: "This file has no usable name",
};

export function uploadMessageFor(error: object): string {
  const code = "code" in error && typeof error.code === "string" ? error.code : "";
  return MESSAGES[code] ?? "Something went wrong. Try again.";
}
