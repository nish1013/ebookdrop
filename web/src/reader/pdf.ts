import { getDocument, GlobalWorkerOptions } from "pdfjs-dist";
import type { PDFDocumentProxy } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { PDF_SCALE } from "./reader.constants";
import type { Pages } from "./reader.types";

GlobalWorkerOptions.workerSrc = workerUrl;

export async function openPdf(file: Blob, container: HTMLElement): Promise<Pages> {
  const data = new Uint8Array(await file.arrayBuffer());
  const pdf = await getDocument({ data, enableXfa: false }).promise;
  const canvas = document.createElement("canvas");
  canvas.setAttribute("role", "img");
  container.append(canvas);
  let current = 0;

  async function show(number: number): Promise<void> {
    if (number < 1 || number > pdf.numPages) return;
    await render(pdf, number, canvas);
    current = number;
  }

  await show(1);
  return { previous: () => show(current - 1), next: () => show(current + 1) };
}

async function render(pdf: PDFDocumentProxy, number: number, canvas: HTMLCanvasElement): Promise<void> {
  const page = await pdf.getPage(number);
  const viewport = page.getViewport({ scale: PDF_SCALE });
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await page.render({ canvas, viewport }).promise;
  canvas.setAttribute("aria-label", `Page ${number}`);
}
