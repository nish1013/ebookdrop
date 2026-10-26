# Commands

Timeline: [eventstorm.md](eventstorm.md). One section per command. `When` is the command, `Then` is
its events.

## Identity (draft)

### S1. SignUp: As a visitor I want an account so that my library is private

Rules
- R1 One email address has one account. Case and outer spaces do not count.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | No account for `ana@example.com` | Ana signs up with `ana@example.com` | `ReaderSignedUp`: Ana has an empty library |
| AC2 | An account for `ana@example.com` | Ben signs up with ` ANA@example.com` | Ben sees "This email already has an account" |
| AC3 | No account for `ana@example.com` | Two sign-ups with `ana@example.com` arrive in the same second | One `ReaderSignedUp`. The other sign-up sees AC2. |

Questions: Q13.

### S2. SignIn: As a reader I want to sign in so that I reach my library

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana has an account | Ana signs in with the right password | `ReaderSignedIn`: Ana sees her library |
| AC2 | Ana has an account | Ana signs in with a wrong password | Ana sees "Email or password is wrong" |

Questions: Q13.

### S3. SignOut: As a reader I want to sign out so that nobody else uses my session

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana is signed in | Ana signs out | `ReaderSignedOut`: the next request from the old session gets the sign-in page |
| AC2 | Ana signed in longer ago than the session length | Ana opens her library | `ReaderSignedOut`: Ana sees the sign-in page |

Questions: Q13.

## Library (draft)

### S4. UploadBook: As a reader I want to upload an EPUB or PDF so that it becomes a book

Rules
- R2 Only EPUB and PDF are accepted, checked by content, never by extension.
- R3 A file is 50 MB or smaller.
- R4 A file with DRM is rejected with a reason.
- R5 A library row exists only after the last byte arrives.
- R6 The same file twice by one reader: see Q1.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana is signed in | Ana uploads `dune.epub`, 2 MB | `UploadReceived`: Ana sees `dune.epub`, "Processing" |
| AC2 | Ana is signed in | Ana uploads `notes.epub`, a ZIP with no EPUB `mimetype` | `UploadRejected(not_epub_or_pdf)`: "This file is not an EPUB or PDF" |
| AC3 | Ana is signed in | Ana uploads `atlas.pdf`, 51 MB | `UploadRejected(too_large)`: "Files must be 50 MB or smaller" |
| AC4 | Ana is signed in | Ana uploads `store.epub` with `META-INF/encryption.xml` | `UploadRejected(drm_protected)`: "This file has DRM" |
| AC5 | Ana uploads `dune.epub` | The network stops at 1 MB of 2 MB | `UploadAbandoned`: Ana's library has no `dune.epub` row |
| AC6 | Ana owns `dune.epub`, sha256 `9f2c…` | Ana uploads the same bytes as `dune-copy.epub` | `DuplicateUploadDetected`: result from Q1 |
| AC7 | Ana is signed out | A request uploads `dune.epub` | The app answers 401. No event. |

Questions: Q1, Q3, Q5, Q6, Q10, Q11.

### S6. MarkBookReady: As a reader I want a converted book in my library so that I can read it

Policy P3: whenever `EpubNormalised` or `PdfKeptAsIs`, mark the book ready. ⚠ The command crosses
two draft contexts.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | `dune.epub` is "Processing", `EpubNormalised` with title "Dune", author "Frank Herbert" | P3 runs | `BookReady`: Ana sees "Dune", Frank Herbert, its cover |
| AC2 | `BookReady` for `dune.epub` | P3 runs again for the same conversion | No second `BookReady`. One row. |
| AC3 | `dune.epub` was received at 10:00:00 | `BookReady` at 10:02:30 | `BookReadyLate` in the metric report |
| AC4 | Ana deleted `dune.epub` during conversion | `EpubNormalised` arrives | No `BookReady`. No row comes back. |

Questions: Q4, Q7, Q15.

### S7. FailStuckConversion: As a reader I want a stuck upload to fail so that I can try again

Policy P2: whenever `ProcessingDeadlinePassed`, fail the conversion. ⚠ The command crosses two
draft contexts.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | `dune.epub` is "Processing" since 10:00, deadline is the conversion timeout plus a margin | The deadline passes | `ConversionFailed(stuck)`: Ana sees "Failed: try again" |
| AC2 | `dune.epub` became `BookReady` at 10:00:40 | The deadline passes | No event. The book stays ready. |

Questions: Q12, Q14.

### S8. OpenBook: As a reader I want to read a book in the browser so that I need no other app

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana owns ready book `b1` | Ana opens `b1` | `BookOpened`: chapter 1 or page 1 shows |
| AC2 | Ana owns `b1` | Ben opens `b1` | `BookAccessDenied`: Ben gets the answer from Q9 |
| AC3 | Ana owns ready book `b2`, and the reader view cannot render it | Ana opens `b2` | `BookOpenFailed`: result from Q8 |
| AC4 | Ana owns `b1`, which holds a `<script>` tag | Ana opens `b1` | `BookOpened`. The script does not run. |

Questions: Q8, Q9.

### S9. DeleteBook: As a reader I want to delete a book so that my file is gone

Rules
- R7 After a delete, no copy of the file stays in the reader's library or storage.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana owns ready book `b1` | Ana deletes `b1` | `BookDeleted`: `b1` is gone from her list |
| AC2 | `b1` is "Processing" | Ana deletes `b1` | `BookDeletedDuringConversion`: `b1` is gone, and S6 AC4 holds |
| AC3 | Ana owns `b1` | Ben deletes `b1` | Ben gets the answer from Q9. `b1` stays. |

Questions: Q2, Q15.

### S10. RemoveBookFiles: As a reader I want my deleted files removed so that my data is gone

Policy P4: whenever `BookDeleted` or `AccountDeleted`, remove the files.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | `BookDeleted` for `b1` | P4 runs | `BookFilesRemoved`: the original, the converted file and the cover of `b1` are gone |
| AC2 | P4 removed 2 of 3 files, then the process stopped | P4 runs again | `BookFilesRemoved` once. The third file is gone. |

Questions: Q2, Q16.

### S11. CleanFailedUpload: As the owner I want files of failed uploads removed so that disk holds no waste

Policy P5: whenever `ConversionFailed` is older than the keep time, remove its files.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | `ConversionFailed` for `bad.pdf` 8 days ago, keep time 7 days (assumed) | P5 runs | `FailedUploadCleanedUp`: the file is gone, the "Failed" row stays |

Questions: Q2.

## Identity and Library

### S12. DeleteAccount: As a reader I want to delete my account so that no data of mine stays

⚠ The command crosses two draft contexts.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | Ana has an account and 3 books | Ana deletes her account | `AccountDeleted`: Ana cannot sign in, and P4 removes the files of all 3 books |
| AC2 | `AccountDeleted` for Ana | Ana signs up again with `ana@example.com` | `ReaderSignedUp`: an empty library |

Questions: Q2.

## Conversion (draft)

### S5. ConvertBook: As a reader I want my file made readable so that it opens in the browser

Policy P1: whenever `UploadReceived`, convert the file.

Rules
- R8 Each file converts in its own sandbox, with no network and a time limit.
- R9 An EPUB is normalised. A PDF is kept as it is.

| AC | Given | When | Then |
|---|---|---|---|
| AC1 | `UploadReceived` for `dune.epub` | P1 runs | `ConversionQueued`, `ConversionStarted`, `EpubNormalised`, `BookDetailsExtracted` |
| AC2 | `UploadReceived` for `atlas.pdf` | P1 runs | `PdfKeptAsIs`, `BookDetailsExtracted` |
| AC3 | `UploadReceived` for `broken.epub`, a cut ZIP | P1 runs | `ConversionFailed(malformed)`: "This file is damaged" |
| AC4 | `UploadReceived` for `slow.epub` | The conversion runs past the timeout | `ConversionFailed(timed_out)` |
| AC5 | `UploadReceived` for `evil.epub`, which opens a network socket | P1 runs | `SandboxEscapeBlocked`, then `ConversionFailed(crashed)` |
| AC6 | `UploadReceived` for `notitle.epub`, with no title and no cover | P1 runs | Result from Q4 |
| AC7 | P1 ran once for `dune.epub` | P1 runs a second time for the same upload | One `EpubNormalised`. |

Questions: Q4, Q8, Q10, Q11, Q12.

## Failure checklist

| Check | Where |
|---|---|
| A crash between steps | P1 after `UploadReceived` (Q11), P4 after 2 of 3 files (S10 AC2), a dead worker (S7) |
| Retries and duplicates | S4 AC6, S5 AC7, S6 AC2, S10 AC2 |
| Ordering and concurrency | S1 AC3, S9 AC2 with S6 AC4 |
| Poison input | S4 AC2-AC4, S5 AC3-AC5, S8 AC4 |
| An event with no command | `ProcessingDeadlinePassed` is time. `BookReadyLate` is derived. |
| An owner per decision | The book status during conversion: Q14 |

## Questions

| Q | Command | Question | Kind | Status | Decision |
|---|---|---|---|---|---|
| Q1 | S4 | The same file twice: reject, keep both, or replace? | product | open | |
| Q2 | S9-S12 | Book delete and account delete in release 1? | product | open | |
| Q3 | S4 | A storage limit per reader? | product | open | |
| Q4 | S5, S6 | No title or cover: failure, or a fallback? | product | open | |
| Q5 | S4 | Clock start, and do rejects count in the 95%? | product | open | |
| Q6 | S4 | Is a password PDF a DRM reject? | product | open | |
| Q7 | S6 | A late book: an alert, or a report only? | product | open | |
| Q8 | S8 | A ready book that does not open: back to failed? | product | open | |
| Q9 | S8, S9 | Another reader's book: 404 or 403? | product | open | |
| Q10 | S4, S5 | The size check: before or after the transfer ends? | tech | open | |
| Q11 | S4, S5 | A crash after `UploadReceived` and before the queue. | tech | open | |
| Q12 | S5, S7 | The timeout value and the stuck deadline. | tech | open | |
| Q13 | S1-S3 | Sign-in method and session length. | tech | open | |
| Q14 | S6, S7 | Who owns the book status during conversion? | boundary | open | |
| Q15 | S6, S9 | A delete during conversion, then the result arrives. | boundary | open | |
| Q16 | S10 | Row gone, file stays: the order of a delete. | tech | open | |
| Q17 | S4, S5 | A corrupt file: reject at intake, or fail in conversion? | boundary | open | |

## Out of scope

| Item | Why |
|---|---|
| Copyright takedown | Libraries are private. The brief has no takedown. |
| A retry button | The brief cuts the retry queue. The reader uploads again. |
| Password reset by email | Depends on Q13. |
