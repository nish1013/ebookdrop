import io
import random
import struct
import zipfile
import zlib

import pikepdf

EPUB_MIMETYPE = b"application/epub+zip"
CONTAINER = b"""<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
CHAPTER = b"<html xmlns='http://www.w3.org/1999/xhtml'><body><p>Dune</p></body></html>"
BLANK_CHAPTER = b"<html xmlns='http://www.w3.org/1999/xhtml'><body> </body></html>"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
DRM_ALGORITHM = "http://www.w3.org/2001/04/xmlenc#aes128-cbc"
FONT_OBFUSCATION = "http://www.idpf.org/2008/embedding"


def encryption_xml(algorithm: str) -> bytes:
    return f"""<?xml version="1.0"?>
<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container"
            xmlns:enc="http://www.w3.org/2001/04/xmlenc#">
  <enc:EncryptedData>
    <enc:EncryptionMethod Algorithm="{algorithm}"/>
    <enc:CipherData><enc:CipherReference URI="OEBPS/ch1.xhtml"/></enc:CipherData>
  </enc:EncryptedData>
</encryption>""".encode()


def png(width: int = 4, height: int = 6) -> bytes:
    """A small red PNG image."""
    rows = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        PNG_MAGIC
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(rows))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind + data)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)


def package(title: str | None, author: str | None, cover: bool) -> bytes:
    """The OPF of a one-chapter EPUB, with the details given."""
    details = "".join(
        [
            f"<dc:title>{title}</dc:title>" if title is not None else "",
            f"<dc:creator>{author}</dc:creator>" if author is not None else "",
            '<meta name="cover" content="cover"/>' if cover else "",
        ]
    )
    cover_item = (
        '<item id="cover" href="cover.png" media-type="image/png"/>' if cover else ""
    )
    return f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="id">urn:uuid:5f1c6d43-9a0e-4c55-8a40-3f0d7c0f0a11</dc:identifier>
    <dc:language>en</dc:language>{details}
  </metadata>
  <manifest>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>{cover_item}
  </manifest>
  <spine><itemref idref="ch1"/></spine>
</package>""".encode()


def epub(
    *,
    mimetype: bool = True,
    encryption: str | None = None,
    padding: int = 0,
    seed: int = 0,
    title: str | None = None,
    author: str | None = None,
    cover: bool = False,
    blank: bool = False,
) -> bytes:
    """A small valid EPUB. `padding` adds stored bytes that `seed` makes unique.

    `blank` gives a first page with nothing to show.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        if mimetype:
            book.writestr("mimetype", EPUB_MIMETYPE, zipfile.ZIP_STORED)
        book.writestr("META-INF/container.xml", CONTAINER, zipfile.ZIP_DEFLATED)
        if encryption is not None:
            book.writestr(
                "META-INF/encryption.xml",
                encryption_xml(encryption),
                zipfile.ZIP_DEFLATED,
            )
        book.writestr(
            "OEBPS/content.opf", package(title, author, cover), zipfile.ZIP_DEFLATED
        )
        chapter = BLANK_CHAPTER if blank else CHAPTER
        book.writestr("OEBPS/ch1.xhtml", chapter, zipfile.ZIP_DEFLATED)
        if cover:
            book.writestr("OEBPS/cover.png", png(), zipfile.ZIP_STORED)
        book.writestr("OEBPS/seed.txt", str(seed), zipfile.ZIP_STORED)
        if padding:
            pad = random.Random(seed).randbytes(padding)  # noqa: S311
            book.writestr("OEBPS/pad.bin", pad, zipfile.ZIP_STORED)
    return buffer.getvalue()


def cut(data: bytes, share: float) -> bytes:
    return data[: int(len(data) * share)]


def pdf(
    *,
    user: str = "",
    owner: str | None = None,
    allow_print: bool = True,
    title: str | None = None,
) -> bytes:
    """A one-page PDF. An owner password encrypts it with the given limits."""
    document = pikepdf.new()
    document.add_blank_page()
    if title is not None:
        document.docinfo["/Title"] = title
    buffer = io.BytesIO()
    if owner is None:
        document.save(buffer)
    else:
        allow = pikepdf.Permissions(print_lowres=allow_print, print_highres=allow_print)
        document.save(
            buffer, encryption=pikepdf.Encryption(owner=owner, user=user, allow=allow)
        )
    return buffer.getvalue()
