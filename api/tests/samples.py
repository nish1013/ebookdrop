import io
import random
import zipfile

import pikepdf

EPUB_MIMETYPE = b"application/epub+zip"
CONTAINER = b"""<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
CHAPTER = b"<html xmlns='http://www.w3.org/1999/xhtml'><body><p>Dune</p></body></html>"
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


def epub(
    *,
    mimetype: bool = True,
    encryption: str | None = None,
    padding: int = 0,
    seed: int = 0,
) -> bytes:
    """A small valid EPUB. `padding` adds stored bytes that `seed` makes unique."""
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
        book.writestr("OEBPS/ch1.xhtml", CHAPTER, zipfile.ZIP_DEFLATED)
        book.writestr("OEBPS/seed.txt", str(seed), zipfile.ZIP_STORED)
        if padding:
            pad = random.Random(seed).randbytes(padding)  # noqa: S311
            book.writestr("OEBPS/pad.bin", pad, zipfile.ZIP_STORED)
    return buffer.getvalue()


def cut(data: bytes, share: float) -> bytes:
    return data[: int(len(data) * share)]


def pdf(*, user: str = "", owner: str | None = None, allow_print: bool = True) -> bytes:
    """A one-page PDF. An owner password encrypts it with the given limits."""
    document = pikepdf.new()
    document.add_blank_page()
    buffer = io.BytesIO()
    if owner is None:
        document.save(buffer)
    else:
        allow = pikepdf.Permissions(print_lowres=allow_print, print_highres=allow_print)
        document.save(
            buffer, encryption=pikepdf.Encryption(owner=owner, user=user, allow=allow)
        )
    return buffer.getvalue()
