# Stories

> "as an e-reader user I can upload my own files and they will convert to proper format and appear in my app"

Brief: [brief.md](brief.md). Scope is the brief's Scope In.

## Picture

```
ebookdrop: a reader uploads an EPUB or PDF and reads it in a web library.

reader --upload--> [check type, size, quota, dedup] --> Processing --convert--> Ready --open--> reader view
                          └--reject--> error shown          └--damaged / timeout--> Failed: reason

S1  Account and sign-in     one email, one private library
S2  Upload a file           EPUB or PDF, 50 MB, 1 GB
S3  Upload status           Processing, Ready or Failed
S4  Library                 title, author, cover, status
S5  Read in the browser     chapter 1 or page 1, no scripts
S6  Delete                  book or account, files removed

draft contexts (confirmed at step 5)
+-----------+      +-----------------------+      +------------+      +----------+
| Identity  |----->| Library               |----->| Conversion |      | Reader   |
| S1        |      | S2 S3 S4 S6           |<-----| S3         |      | S5       |
+-----------+      +-----------------------+      +------------+      +----------+
open: Conversion is a context, or a port in Library (no invariant of its own?)
open: Reader is a context, or a read model over Library
open: who owns the upload status, Library or Conversion
```

## Example map

### S1. As a reader I want to create an account and sign in so that my library is mine

Rules
- R1 One email address has one account.
- R2 A reader sees only the books of their own account.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | No account for `ana@example.com` | Ana signs up with `ana@example.com` and a 12-character password | Ana is signed in to an empty library |
| AC2 | An account for `ana@example.com` | Ben signs up with `ANA@example.com ` | Ben sees "This email already has an account" |
| AC3 | Ana is signed in and owns book `b1` | Ben requests book `b1` | Ben gets 404 |

Questions: Q1, Q2.

### S2. As a reader I want to upload an EPUB or PDF file so that it becomes a book

Rules
- R3 Only EPUB and PDF files are accepted, checked by content.
- R4 A file is 50 MB or smaller.
- R5 The same file uploaded twice by one reader gives one book.
- R13 The files of one reader total 1 GB or less.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana is signed in | Ana uploads `dune.epub`, 2 MB | Ana sees `dune.epub` with status "Processing" |
| AC2 | Ana is signed in | Ana uploads `notes.epub`, which is a ZIP with no EPUB mimetype | Ana sees "This file is not an EPUB or PDF" |
| AC3 | Ana is signed in | Ana uploads `atlas.pdf`, 51 MB | Ana sees "Files must be 50 MB or smaller" |
| AC4 | Ana has book "Dune" from `dune.epub` | Ana uploads the same bytes as `dune-copy.epub` | Ana sees the existing book "Dune". Her library has one "Dune" |
| AC5 | Ana stores 990 MB | Ana uploads `atlas.pdf`, 20 MB | Ana sees "Your library is full (1 GB)" |

Questions: Q3, Q4.

### S3. As a reader I want to see the status of each upload so that I know when a book is ready

Rules
- R6 An upload is Processing, Ready or Failed. Failed shows a reason.
- R7 An upload leaves Processing within 2 minutes.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | `dune.epub` is Processing | The conversion ends with no error | The status is "Ready" |
| AC2 | `broken.epub` is Processing | The converter reports a damaged archive | The status is "Failed: the file is damaged" |
| AC3 | `bomb.pdf` is Processing | The converter runs for more than 60 seconds | The status is "Failed: the file took too long to read" |

Questions: Q5, Q6.

### S4. As a reader I want to see my library so that I find my books

Rules
- R8 Each Ready book shows a title, an author and a cover.
- R11 Processing and Failed uploads show in the same list with their status.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana has "Dune" by Frank Herbert, Ready, with a cover | Ana opens the library | Ana sees "Dune", "Frank Herbert" and the cover |
| AC2 | `scan_0042.pdf` is Ready and has no title or author | Ana opens the library | Ana sees "scan_0042", "Unknown author" and a cover |
| AC3 | `broken.epub` is Failed and `dune.epub` is Processing | Ana opens the library | Ana sees both files in the list, each with its status |

Questions: Q7.

### S5. As a reader I want to read a book in the browser so that I need no other app

Rules
- R9 A Ready book opens in the browser reader.
- R10 Book content cannot run scripts in the app.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | "Dune" is Ready | Ana opens "Dune" | Ana sees chapter 1 |
| AC2 | `atlas.pdf` is Ready | Ana opens "Atlas" | Ana sees page 1 |
| AC3 | `evil.epub` holds `<script>` in chapter 1 | Ana opens it | The script does not run. Ana sees the text |

Questions: Q8.

### S6. As a reader I want to delete a book or my account so that my files leave the app

Rules
- R12 A delete removes the file, the cover and the rows at once.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana has "Dune", Ready | Ana deletes "Dune" | "Dune" is not in her library. A request for its file gets 404 |
| AC2 | Ana has 3 books | Ana deletes her account | Ana is signed out. A sign-in with `ana@example.com` fails. Her 3 files are gone from storage |

Questions: Q10.

## Questions

| Q | Story | Question | Status | Decision |
|---|---|---|---|---|
| Q1 | S1 | How does a reader sign in? Pick: email and password, hashed with Argon2id. | Resolved | Email and password, Argon2id (D8). |
| Q2 | S1 | Can a reader delete a book or the account? Pick: delete a book and delete the account are in release 1, for personal data. | Resolved | Book delete and account delete in release 1 (D9). S6 added. |
| Q3 | S2 | What is the dedup key? Pick: SHA-256 of the bytes, per reader. | Resolved | SHA-256 of the bytes, per reader (D10). |
| Q4 | S2 | Is there a storage limit per reader? Pick: 1 GB per reader. | Resolved | 1 GB per reader (D11). R13, S2 AC5 added. |
| Q5 | S3 | The server crashes after it stores the file and before conversion. Pick: a worker picks Processing uploads from the table. One retry, then Failed. | Open | |
| Q6 | S3 | A file always crashes the converter. Pick: no retry after a timeout or a crash. Status Failed at once. | Open | |
| Q7 | S4 | What is the cover of a PDF or of an EPUB with no cover? Pick: PDF page 1 as an image. An EPUB with no cover gets a generated title card. | Open | |
| Q8 | S5 | How does the reader isolate book content? Pick: strip scripts at conversion, and show content in a sandboxed iframe with a strict CSP. | Open | |
| Q9 | S1 | A reader forgets the password. Release 1 has no email service. Pick: no reset in release 1. The sign-in page says so. | Open | |
| Q10 | S6 | Ana deletes `dune.epub` while it is Processing. Pick: the delete removes it at once. The worker then finds no row and drops its result. | Open | |
| Q11 | S2 | Ana uploads the same bytes again after the first upload is Failed. Pick: the new upload replaces the Failed one and starts Processing. | Open | |

## Out of scope

- MOBI, AZW, DOCX and TXT input.
- DRM-protected files.
- Collections, tags and search.
- Reading position sync across devices.
- Shared libraries.
- Retry queue and email notices.
