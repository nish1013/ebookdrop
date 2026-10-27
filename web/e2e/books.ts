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
const CONTAINER =
  '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">' +
  '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>';

export function epub(name: string, seed = name): BookFile {
  const buffer = storedZip([
    { name: "mimetype", data: Buffer.from("application/epub+zip") },
    { name: "META-INF/container.xml", data: Buffer.from(CONTAINER) },
    { name: "OEBPS/ch1.xhtml", data: Buffer.from(CHAPTER) },
    { name: "OEBPS/seed.txt", data: Buffer.from(seed) },
  ]);
  return { name, mimeType: "application/epub+zip", buffer };
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
