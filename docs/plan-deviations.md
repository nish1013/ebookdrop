# Plan deviations

Where the build departs from [plan.md](plan.md), and why. A deviation becomes a decision
only once it is added to [decisions.md](decisions.md).

## D4. A cover read for the library list (PR 2, 2026-10-27)

**In short:** The library list shows each cover from its own read.

- **Plan:** The endpoint table has no cover read. S6 AC1 says Ana sees the cover of a ready book.
- **Built:** `GET /api/books/{id}/cover` answers 200 with the PNG, or 404 `book_not_found`. The list gives `cover_url` only when a cover exists.
- **Why:** A cover inside the list answer makes each list read carry every cover. The read filters by the owner, so a foreign book gets the same 404 as a missing book.
- **Undo:** Remove the endpoint and `cover_url`. The list then shows a plain cover with the title for every book.

## D5. The converter port defines a PNG cover (PR 2, 2026-10-27)

**In short:** Every cover that the converter gives is a PNG file.

- **Plan:** The plan names `ConverterPort` but no cover format.
- **Built:** `Conversion.cover` is a PNG path or none. The cover read answers `image/png` with `nosniff`.
- **Why:** One raster format needs no stored media type. An SVG cover from an untrusted book could carry a script.
- **Undo:** Store a media type per cover, and allow a fixed list of raster types.

## D6. The quota test starts at 1010 MiB, not 990 MB (PR 3, 2026-10-27)

**In short:** The full-library test starts with more stored bytes, because the limits count in binary units.

- **Plan:** S4 AC9 puts a 20 MB upload on 990 MB. The guard in aggregates.md is 1073741824 bytes, and the file limit is 50 MiB.
- **Built:** The test stores 1010 MiB and uploads about 20 MiB, and it asserts that the sum exceeds 1 GiB. AC3 sends 51 MiB.
- **Why:** 990 MiB plus 20 MiB is 1010 MiB, which is under 1024 MiB, so the upload passes. Decimal units break AC10 instead: 980 MB plus 30 MB already exceeds 1000 MB.
- **Undo:** Change the AC9 values in commands.md to 1010 MB, or move both limits to decimal units and change AC10.

## D7. The inspect answers for time-outs and outages (PR 3, 2026-10-27)

**In short:** A file that runs the sandbox out of time or memory counts as damaged.

- **Plan:** Decision 19 lists the reasons and the 10 s limit. The endpoint table has no answer for a stopped transfer or a sandbox that does not start.
- **Built:** A time-out or a memory kill gives `damaged` and removes the container, with the 10 s clock from the container start. A Docker failure or a start past 30 s answers 503 `inspect_unavailable`, and a stopped transfer answers 400 `upload_abandoned`.
- **Why:** The reason list has no time-out word, and a zip bomb is a damaged file. An outage must not reject a good file. The file goes to the container on stdin, so no host folder is mounted.
- **Undo:** Add a reason word for the time-out, and map it in `DockerInspector`.

## D8. Font obfuscation is not DRM (PR 3, 2026-10-27)

**In short:** An EPUB whose `encryption.xml` hides fonts only is accepted.

- **Plan:** S4 AC4 rejects an EPUB with `META-INF/encryption.xml` as `drm_protected`.
- **Built:** The check reads the algorithms in `encryption.xml`, and font obfuscation only gives `epub`. Any other algorithm, or a file that does not parse, gives `drm_protected`.
- **Why:** The EPUB standard uses `encryption.xml` for font obfuscation, and the text stays readable. A reject by file name refuses those DRM-free books (R4, decision 3).
- **Undo:** Remove `_fonts_only` from `sandbox_check.py`. Every `encryption.xml` then gives `drm_protected`.

## D9. The EPUB page 1 check reads the page, it does not draw it (PR 4, 2026-10-27)

**In short:** An EPUB is ready when its first page holds text or an image after Calibre normalises it.

- **Plan:** Decision 15 and R12 render page 1 in the sandbox before `BookReady`. The stack names `pdftoppm` for this.
- **Built:** A PDF renders page 1 with `pdftoppm`. An EPUB parses the first spine page of the Calibre output, and passes when its body has text or an image.
- **Why:** A raster render of an EPUB needs Calibre's Qt WebEngine, a browser engine with many processes, and the sandbox allows 64. The parse runs in the same container and the same time limit.
- **Undo:** Render the EPUB to PDF with `ebook-convert`, then run `pdftoppm` on page 1. Raise the process limit for that container if WebEngine needs it.

## D10. The sandbox kills a network socket, and the test uses a hostile converter (PR 4, 2026-10-27)

**In short:** A conversion that opens an internet socket stops at once and fails as crashed.

- **Plan:** S5 AC5 gives `evil.epub`, which opens a network socket, `SandboxEscapeBlocked` and then `ConversionFailed(crashed)`. Event 14 also names disk access.
- **Built:** The convert container runs with Docker's default seccomp profile plus one change: an IPv4 or IPv6 socket kills the process. The test image swaps `ebook-convert` for a hostile program that connects out, hangs or floods the output, and a probe proves the block.
- **Why:** A book file cannot run code, so only an exploited parser opens a socket, and a test cannot ship a real exploit. With no network alone, a connect fails quietly and looks like a damaged file. The root is read-only, so a disk write fails and has no event.
- **Undo:** Remove the profile from `convert_command`. A socket then fails with no network, and the book fails as malformed.

## D11. A file name with no printable letter gives the title "Untitled" (PR 4, 2026-10-27)

**In short:** Every ready book has a printable title, also when its file name has none.

- **Plan:** Decision 11 falls back to the file name without its extension.
- **Built:** Titles and authors lose control characters and extra spaces, and stop at 255 characters. A file name with nothing printable left gives "Untitled".
- **Why:** The intake keeps control characters in a file name, and the title comes from an untrusted book. The list must show a title that is never empty.
- **Undo:** Refuse such a file name at intake with `invalid_file_name`. Then remove `UNTITLED`.
