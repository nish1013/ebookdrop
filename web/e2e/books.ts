import { crc32 } from "node:zlib";

export interface BookFile {
  name: string;
  mimeType: string;
  buffer: Buffer;
}

interface Entry {
  name: string;
  data: Buffer;
}

const CHAPTER = "<html xmlns='http://www.w3.org/1999/xhtml'><body><p>Dune</p></body></html>";
const BLANK_CHAPTER = "<html xmlns='http://www.w3.org/1999/xhtml'><body> </body></html>";
const CONTAINER =
  '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">' +
  '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>';

export interface EpubDetails {
  title?: string;
  author?: string;
  blank?: boolean;
  chapter?: string;
  svgPage?: string;
}

function opf({ title, author, svgPage }: EpubDetails): string {
  const details =
    (title ? `<dc:title>${title}</dc:title>` : "") + (author ? `<dc:creator>${author}</dc:creator>` : "");
  return (
    '<?xml version="1.0" encoding="utf-8"?>' +
    '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">' +
    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">' +
    `<dc:identifier id="id">urn:uuid:5f1c6d43-9a0e-4c55-8a40-3f0d7c0f0a11</dc:identifier><dc:language>en</dc:language>${details}` +
    '</metadata><manifest><item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>' +
    (svgPage ? '<item id="page" href="page.svg" media-type="image/svg+xml"/>' : "") +
    `</manifest><spine>${svgPage ? '<itemref idref="page"/>' : ""}<itemref idref="ch1"/></spine></package>`
  );
}

export function epub(name: string, seed = name, details: EpubDetails = {}): BookFile {
  const buffer = storedZip([
    { name: "mimetype", data: Buffer.from("application/epub+zip") },
    { name: "META-INF/container.xml", data: Buffer.from(CONTAINER) },
    { name: "OEBPS/content.opf", data: Buffer.from(opf(details)) },
    { name: "OEBPS/ch1.xhtml", data: Buffer.from(details.chapter ?? (details.blank ? BLANK_CHAPTER : CHAPTER)) },
    ...(details.svgPage ? [{ name: "OEBPS/page.svg", data: Buffer.from(details.svgPage) }] : []),
    { name: "OEBPS/seed.txt", data: Buffer.from(seed) },
  ]);
  return { name, mimeType: "application/epub+zip", buffer };
}

export function pdf(name: string, text: string): BookFile {
  const stream = `BT /F1 24 Tf 72 720 Td (${text}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((object, index) => {
    offsets.push(body.length);
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return { name, mimeType: "application/pdf", buffer: Buffer.from(body, "latin1") };
}

function storedZip(entries: Entry[]): Buffer {
  const locals: Buffer[] = [];
  const centrals: Buffer[] = [];
  let offset = 0;
  for (const { name, data } of entries) {
    const fileName = Buffer.from(name);
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(fileName.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(fileName.length, 28);
    central.writeUInt32LE(offset, 42);
    locals.push(local, fileName, data);
    centrals.push(central, fileName);
    offset += local.length + fileName.length + data.length;
  }
  const directory = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(directory.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, directory, end]);
}
