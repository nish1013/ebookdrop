"""The check that runs inside the inspect container.

It reads one file from stdin and prints one verdict word. It imports no app code,
because the image holds this file only. An error it does not name ends the process
with `CRASH_EXIT`, which the adapter reads as a damaged file.
"""

import io
import os
import sys
import zipfile
import zlib
from xml.etree import ElementTree

MAX_BYTES = 50 * 1024 * 1024
CRASH_EXIT = 3
ZIP_MAGIC = b"PK\x03\x04"
PDF_MAGIC = b"%PDF-"
PDF_HEADER_WINDOW = 1024
EPUB_MIMETYPE = b"application/epub+zip"
ENCRYPTION = "META-INF/encryption.xml"
XMLENC = "{http://www.w3.org/2001/04/xmlenc#}"
# Font obfuscation hides fonts from copy, not the text: the book stays readable.
FONT_OBFUSCATION = {
    "http://www.idpf.org/2008/embedding",
    "http://ns.adobe.com/pdf/enc#RC",
}
_ZIP_DAMAGE = (zipfile.BadZipFile, zlib.error, EOFError, OSError, ValueError)


def check(data: bytes) -> str:
    """Return `epub`, `pdf` or a refusal word for the bytes of one file."""
    if data.startswith(ZIP_MAGIC):
        return _check_epub(data)
    if PDF_MAGIC in data[:PDF_HEADER_WINDOW]:
        return _check_pdf(data)
    return "not_epub_or_pdf"


def main() -> None:
    """Read the file from stdin and print its verdict."""
    sys.excepthook = _crash
    print(check(sys.stdin.buffer.read(MAX_BYTES + 1)))


def _crash(*_: object) -> None:
    os._exit(CRASH_EXIT)


def _check_epub(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as book:
            if not _has_epub_mimetype(book):
                return "not_epub_or_pdf"
            if book.testzip() is not None:
                return "damaged"
            if ENCRYPTION in book.namelist() and not _fonts_only(book.read(ENCRYPTION)):
                return "drm_protected"
    except (*_ZIP_DAMAGE, NotImplementedError, RuntimeError):
        return "damaged"
    return "epub"


def _has_epub_mimetype(book: zipfile.ZipFile) -> bool:
    if "mimetype" not in book.namelist():
        return False
    with book.open("mimetype") as mimetype:
        return mimetype.read(len(EPUB_MIMETYPE) + 2).strip() == EPUB_MIMETYPE


def _fonts_only(encryption: bytes) -> bool:
    try:
        root = ElementTree.fromstring(encryption)  # noqa: S314
    except ElementTree.ParseError:
        return False
    algorithms = [
        method.get("Algorithm") for method in root.iter(f"{XMLENC}EncryptionMethod")
    ]
    return bool(algorithms) and all(a in FONT_OBFUSCATION for a in algorithms)


def _check_pdf(data: bytes) -> str:
    import pikepdf

    try:
        with pikepdf.open(io.BytesIO(data)) as document:
            pages = len(document.pages)
    except pikepdf.PasswordError:
        return "password_protected"
    except pikepdf.PdfError:
        return "damaged"
    return "pdf" if pages else "damaged"


if __name__ == "__main__":
    main()
