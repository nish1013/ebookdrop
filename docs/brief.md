# Brief: upload own books to a web library

> "as an e-reader user I can upload my own files and they will convert to proper format and appear in my app"

## Brief

| Field | Content |
|---|---|
| Goal | A reader uploads a file. The file converts to a readable format and appears in the reader's library. |
| Metric | 95% of uploads appear in the library as readable books within 2 minutes (assumed). Events: `upload_received`, `book_ready`. |
| User | A reader with DRM-free EPUB and PDF files from outside a store (assumed). |
| Now | The reader emails files to a device vendor address, or converts them on a desktop tool and copies them by USB cable. |
| Constraints | Playground time box of 2 weeks (assumed). Stack is open. |
| Risk tier | `high bar`: untrusted file parsing (security) and private libraries (personal data). |
| Stage | `mvp`: the metric tests whether readers want it, in a 2-week box. Parsing, personal data and the quota race get `v1` rigour. |

High-bar checks:

- a file size limit
- a type check by content, not by extension
- conversion in a sandbox with a timeout
- each library visible to its owner only

## Pushback

| Plan says | Concern | I would instead |
|---|---|---|
| "my app" | Vendor e-reader apps have no public API to add books. An own app is the only path that can be built. | Build an own web reader with a library page. Keep the app vendor-neutral. |
| "convert to proper format" | Each extra input format adds a converter and its failure cases. | Accept EPUB and PDF only. Normalise EPUB. Keep PDF as it is. |

## Scope

| In | Cut | Why |
|---|---|---|
| Upload of EPUB and PDF, max 50 MB | MOBI, AZW, DOCX, TXT input | Two formats cover most DRM-free files (assumed). |
| Library list with title, author, cover | Collections, tags, search | The list is enough to show "appears in my app". |
| Read a book in the browser | Sync of reading position across devices | Reading proves the conversion works. |
| Status per upload: processing, ready, failed with reason | Retry queue, email notices | A visible failure reason is enough for release 1. |
| One account per reader | Shared libraries, DRM-protected files | DRM removal is out of scope and has legal risk. |
