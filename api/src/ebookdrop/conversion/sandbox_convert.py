"""The conversion that runs inside the convert container.

It reads one file from stdin and writes a tar stream to stdout: `details.json`, the
normalised `book.epub` for an EPUB, and `cover.png` when the book has a cover. A PDF
stays as it is, so its bytes do not come back. A failure ends the process with its
exit code and writes nothing. It imports no app code, because the image holds the
sandbox files only.
"""

import io
import json
import os
import posixpath
import signal
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

MAX_BYTES = 50 * 1024 * 1024
CRASH_EXIT = 3
MALFORMED_EXIT = 4
UNREADABLE_EXIT = 5
ESCAPE_EXIT = 6
WORK = Path("/tmp/convert")  # noqa: S108
PDF_MAGIC = b"%PDF-"
PDF_HEADER_WINDOW = 1024
# Calibre writes this word in place of a missing title or author.
CALIBRE_PLACEHOLDER = "Unknown"
COVER_BOX = (600, 900)
CONTAINER_NS = "{urn:oasis:names:tc:opendocument:xmlns:container}"
OPF_NS = "{http://www.idpf.org/2007/opf}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"
VISIBLE_TAGS = {"img", "image", "svg", "video", "object"}


class _Failed(Exception):
    def __init__(self, exit_code: int) -> None:
        super().__init__(exit_code)
        self.exit_code = exit_code


def main() -> None:
    """Convert the file on stdin and write the result to stdout."""
    sys.excepthook = _crash
    WORK.mkdir(parents=True, exist_ok=True)
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    try:
        files = convert(data)
    except _Failed as failed:
        sys.exit(failed.exit_code)
    _write_tar(files)


def convert(data: bytes) -> dict[str, bytes]:
    """Return the output files of one book. Raise `_Failed` with an exit code."""
    if PDF_MAGIC in data[:PDF_HEADER_WINDOW]:
        return _convert_pdf(data)
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise _Failed(MALFORMED_EXIT)
    return _convert_epub(data)


def _crash(*_: object) -> None:
    os._exit(CRASH_EXIT)


def _run(command: list[str], failure_exit: int) -> None:
    done = subprocess.run(  # noqa: S603
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if done.returncode == -signal.SIGSYS:
        raise _Failed(ESCAPE_EXIT)
    if done.returncode < 0:
        raise _Failed(CRASH_EXIT)
    if done.returncode != 0:
        raise _Failed(failure_exit)


def _convert_epub(data: bytes) -> dict[str, bytes]:
    source, target = WORK / "source.epub", WORK / "book.epub"
    source.write_bytes(data)
    _run(
        ["ebook-convert", str(source), str(target), "--no-default-epub-cover"],
        MALFORMED_EXIT,
    )
    normalised = target.read_bytes()
    with zipfile.ZipFile(io.BytesIO(normalised)) as book:
        opf_path = _rootfile(book)
        opf = ElementTree.fromstring(book.read(opf_path))  # noqa: S314
        if not _first_page_renders(book, opf, opf_path):
            raise _Failed(UNREADABLE_EXIT)
        files = {
            "details.json": _details("epub", _dc(opf, "title"), _dc(opf, "creator")),
            "book.epub": normalised,
        }
        cover = _cover(book, opf, opf_path)
    if cover is not None:
        files["cover.png"] = cover
    return files


def _rootfile(book: zipfile.ZipFile) -> str:
    container = ElementTree.fromstring(book.read("META-INF/container.xml"))  # noqa: S314
    rootfile = container.find(f".//{CONTAINER_NS}rootfile")
    if rootfile is None:
        raise _Failed(UNREADABLE_EXIT)
    return rootfile.get("full-path", "")


def _manifest_path(opf: ElementTree.Element, opf_path: str, item_id: str) -> str:
    for item in opf.iter(f"{OPF_NS}item"):
        if item.get("id") == item_id:
            href = unquote(item.get("href", ""))
            return posixpath.normpath(posixpath.join(posixpath.dirname(opf_path), href))
    return ""


def _first_page_renders(
    book: zipfile.ZipFile, opf: ElementTree.Element, opf_path: str
) -> bool:
    first = opf.find(f"{OPF_NS}spine/{OPF_NS}itemref")
    if first is None:
        return False
    path = _manifest_path(opf, opf_path, first.get("idref", ""))
    try:
        page = ElementTree.fromstring(book.read(path))  # noqa: S314
    except (KeyError, ElementTree.ParseError):
        return False
    body = next((e for e in page.iter() if _local(e.tag) == "body"), page)
    has_text = any(text.strip() for text in body.itertext())
    return has_text or any(_local(e.tag) in VISIBLE_TAGS for e in body.iter())


def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


def _dc(opf: ElementTree.Element, name: str) -> str | None:
    found = opf.find(f"{OPF_NS}metadata/{DC_NS}{name}")
    text = (found.text or "").strip() if found is not None else ""
    return text if text and text != CALIBRE_PLACEHOLDER else None


def _cover(
    book: zipfile.ZipFile, opf: ElementTree.Element, opf_path: str
) -> bytes | None:
    cover_id = next(
        (
            m.get("content", "")
            for m in opf.iter(f"{OPF_NS}meta")
            if m.get("name") == "cover"
        ),
        "",
    )
    path = _manifest_path(opf, opf_path, cover_id) if cover_id else ""
    if not path or path not in book.namelist():
        return None
    return _png(book.read(path))


def _png(raw: bytes) -> bytes | None:
    from PIL import Image

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.thumbnail(COVER_BOX)
            out = io.BytesIO()
            image.convert("RGB").save(out, "PNG")
    except (OSError, ValueError, Image.DecompressionBombError):
        return None
    return out.getvalue()


def _convert_pdf(data: bytes) -> dict[str, bytes]:
    import pikepdf

    source = WORK / "source.pdf"
    source.write_bytes(data)
    try:
        with pikepdf.open(source) as document:
            title = _text(document.docinfo.get("/Title"))
            author = _text(document.docinfo.get("/Author"))
    except pikepdf.PdfError:
        raise _Failed(MALFORMED_EXIT) from None
    page = WORK / "page"
    _run(
        ["pdftoppm", "-f", "1", "-l", "1", "-r", "36", "-png", "-singlefile"]
        + [str(source), str(page)],
        UNREADABLE_EXIT,
    )
    rendered = page.with_suffix(".png")
    if not rendered.exists() or rendered.stat().st_size == 0:
        raise _Failed(UNREADABLE_EXIT)
    return {"details.json": _details("pdf", title, author)}


def _text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _details(book_format: str, title: str | None, author: str | None) -> bytes:
    return json.dumps(
        {"format": book_format, "title": title, "author": author}
    ).encode()


def _write_tar(files: dict[str, bytes]) -> None:
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


if __name__ == "__main__":
    main()
