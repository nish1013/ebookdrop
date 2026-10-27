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
