import type { FoliateBook } from "foliate-js/view.js";

export type ReaderState = "opening" | "opened" | "missing" | "failed" | "unavailable" | "signed_out";

export interface ReaderMessage {
  state: ReaderState;
}

export interface Pages {
  previous(): Promise<void>;
  next(): Promise<void>;
}

export type Opener = (file: Blob, container: HTMLElement) => Promise<Pages>;

export interface FoliateView extends HTMLElement {
  open(book: FoliateBook): Promise<void>;
  prev(): Promise<void>;
  next(): Promise<void>;
}

export interface SectionData {
  data: unknown;
  type: string;
}
