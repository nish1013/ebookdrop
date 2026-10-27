# Event storm

Brief: [brief.md](brief.md). Four views stormed events from the brief: user (U), business (B),
failure (F), outside (O). Step ①: timeline, pivotal events, hot spots, draft contexts.

## Timeline

```
 ACCOUNT
  1  ReaderSignedUp            U B        ║ pivotal: a private library exists
  2  ReaderSignedIn            U
  3  ReaderSignedOut           U O        also when the session expires
                                                                 ⚡H13 sign-in method, session length
 INTAKE
  4  UploadAbandoned           F          the transfer stopped before the last byte
  5  UploadRejected(reason)    U B F O    too_large · not_epub_or_pdf · drm_protected · password_protected · damaged · over_quota
                                                                 ⚡H6 size check before or after transfer
                                                                 ⚡H7 DRM in PDF, password PDF
                                                                 ⚡H8 a corrupt file: reject here or fail later
                                                                 ⚡H3 storage quota per reader
  6  DuplicateUploadDetected   U B F                             ⚡H1 reject, keep both or replace
  7  UploadReceived            all        ║ pivotal: metric start, upload_received
                                                                 ⚡H5 clock start, denominator
 CONVERSION
  8  ConversionQueued          F O                               ⚡H9 crash between 7 and 9
  9  ConversionStarted         B F O      one sandbox per file
 10  EpubNormalised            all
 11  PdfKeptAsIs               all
 12  BookDetailsExtracted      U B O      title, author, cover   ⚡H4 no title or cover: fail or fallback
 13  ConversionFailed(reason)  all        malformed · unreadable · timed_out · crashed · not_stored · stuck
                                                                 ⚡H10 timeout value inside 2 minutes
 14  SandboxEscapeBlocked      O          a file tried network or disk access
 15  ProcessingDeadlinePassed  F O        time: no ready or failed after the deadline
                                                                 ⚡H11 who finds it, and when
 16  BookReady                 all        ║ pivotal: metric end, book_ready
 17  BookReadyLate             B F O      ready after 2 minutes  ⚡H12 alert or report only
 READING
 18  BookOpened                U B O
 19  BookOpenFailed            F          a ready book does not open  ⚡H14 back to failed?
 20  BookAccessDenied          all        another reader's book  ⚡H15 404 or 403
 REMOVAL
 21  BookDeleted               U B F      ║ pivotal: personal data leaves  ⚡H2 in release 1?
 22  BookDeletedDuringConversion  F       ⚡H16 the result comes back as a ghost book
 23  BookFilesRemoved          F          ⚡H17 row gone, file stays
 24  FailedUploadCleanedUp     O          time: files of failed uploads
 25  AccountDeleted            U B F      ║ pivotal: the library ends  ⚡H2
```

| Merged or dropped | Why |
|---|---|
| `UploadRejectedTooLarge`, `...UnsupportedType`, `...DrmProtected`, `FileTypeRejected` | One fact with a reason: `UploadRejected(reason)`. |
| `UploadAccepted`, `FileStored`, `UploadRetriedByReader` | The same fact as `UploadReceived`. A re-upload is a new upload. |
| `ConversionTimedOut`, `ConversionCrashed`, `ConvertedFileStoreFailed`, `UploadFailed`, `BookMarkedFailed` | One fact with a reason: `ConversionFailed(reason)`. |
| `WorkerLostMidConversion`, `UploadStuckInProcessing` | The outside fact is time: `ProcessingDeadlinePassed`. |
| `MetadataExtracted`, `CoverExtracted`, `MetadataMissing` | One fact: `BookDetailsExtracted`. A missing value is hot spot H4. |
| `MetricTargetMissed` | A view over events 7 and 16. |
| `EmptyLibraryViewed`, `LibraryViewed`, `BookProcessingShown`, `BookFailedShown`, `PageTurned`, `BookClosed` | Views change no state. They are views at step ②. |
| `FileTypeDetected`, `SandboxStarted` | Steps inside a command, not business facts. |
| `CopyrightComplaintReceived` | Out of scope. Libraries are private, and the brief has no takedown. |

## Pivotal events

A pivotal event changes the business phase.

| Event | Phase before | Phase after |
|---|---|---|
| `ReaderSignedUp` | No account | A private, empty library |
| `UploadReceived` | A file in transfer | A file the app owns, and the metric clock runs |
| `BookReady` | A file in processing | A readable book in the library |
| `BookDeleted`, `AccountDeleted` | Personal data held | Personal data removed |

## Words with two meanings

| Word | Meaning 1 | Meaning 2 |
|---|---|---|
| upload | The transfer of bytes from the browser | The record of a file before it is a book |
| book | The file the reader owns | The readable output of the conversion |
| failed | Rejected at intake: the reader must pick another file | Failed in conversion: the file was accepted, then broke |
| ready | `book_ready`: the conversion ended | The book opens in the browser (event 19) |

## Hot spots

| ⚡ | At | Doubt | Kind |
|---|---|---|---|
| H1 | 6 | The same file twice: reject, keep both, or replace? | product |
| H2 | 21, 25 | Book delete and account delete are not in the brief scope. Personal data needs them. | product |
| H3 | 5 | A storage limit per reader? The brief has a per-file limit only. | product |
| H4 | 12 | A file with no title, author or cover: failure, or a fallback? | product |
| H5 | 7 | Does the clock start at the first or last byte? Do rejects count in the 95%? | product |
| H6 | 5 | The 50 MB check runs before the transfer ends, or after? | tech |
| H7 | 5 | DRM in a PDF looks like a password. Is a password PDF a DRM reject? | product |
| H8 | 5, 13 | A broken ZIP or truncated PDF: reject at intake, or fail in conversion? | boundary |
| H9 | 7 to 9 | A crash after `UploadReceived` and before the queue loses the conversion. | tech |
| H10 | 13 | The timeout value must leave room inside 2 minutes. | tech |
| H11 | 15 | A book stays in processing forever when a worker dies. Who marks it failed? | tech |
| H12 | 17 | A late book: an alert, or a number in a report? | product |
| H13 | 1 to 3 | Sign-in method and session length. | tech |
| H14 | 19 | A ready book that does not open hides a metric error. | product |
| H15 | 20 | 403 tells the caller that the book exists. 404 does not. | product |
| H16 | 22 | A delete during conversion, then the conversion result arrives. | boundary |
| H17 | 23 | A delete that removes the row but keeps the file leaves personal data. | tech |

## Draft contexts

Draft. Step ⑤ confirms them from the aggregates.

```
+-----------+      +----------------------------+      +--------------+
| Identity  |----->| Library                    |----->| Conversion   |
| 1 2 3 25  |      | 5 6 7 16 20 21 22 23 24 25 |<-----| 8-15         |
+-----------+      +----------------------------+      +--------------+
                          │ views
                          ▼
                   Reading 18 19    Metrics 17
```

| Draft context | Why | Open |
|---|---|---|
| Identity | Own words: account, password, session. Own rule: one email, one account. | |
| Library | Own words: upload, book, owner. It owns the reader's files and their status. | Who owns the status during conversion? |
| Conversion | Own words: sandbox, normalise, timeout. Pivotal events 7 and 16 frame it. | A context, or a tool behind a port? |
| Reading, Metrics | No state change of their own. | Views, not contexts? |

## Process

Step ②. Each event gets its cause. A cause with no person is a policy.

| # | Event | Command | Role | Policy | View |
|---|---|---|---|---|---|
| 1 | `ReaderSignedUp` | `SignUp` | Visitor | | Sign-up form |
| 2 | `ReaderSignedIn` | `SignIn` | Reader | | Sign-in form |
| 3 | `ReaderSignedOut` | `SignOut` | Reader, or time | | |
| 4 | `UploadAbandoned` | `UploadBook` | Reader | | |
| 5 | `UploadRejected(reason)` | `UploadBook` | Reader | | Upload form with the reason |
| 6 | `DuplicateUploadDetected` | `UploadBook` | Reader | | Library list |
| 7 | `UploadReceived` | `UploadBook` | Reader | | Library list: "Processing" |
| 8-14 | `ConversionQueued` to `SandboxEscapeBlocked` | `ConvertBook` | | P1 whenever `UploadReceived`, convert the file | |
| 13 | `ConversionFailed(stuck)` | `FailStuckConversion` | | P2 whenever `ProcessingDeadlinePassed`, fail the conversion | Library list: "Failed" with reason |
| 15 | `ProcessingDeadlinePassed` | none: time | Clock | | |
| 16 | `BookReady` | `MarkBookReady` | | P3 whenever `EpubNormalised` or `PdfKeptAsIs`, mark the book ready | Library list: title, author, cover |
| 17 | `BookReadyLate` | none: derived from 7 and 16 | | | Metric report |
| 18-20 | `BookOpened`, `BookOpenFailed`, `BookAccessDenied` | `OpenBook` | Reader | | Reader view |
| 21-22 | `BookDeleted`, `BookDeletedDuringConversion` | `DeleteBook` | Reader | | Library list |
| 23 | `BookFilesRemoved` | `RemoveBookFiles` | | P4 whenever `BookDeleted` or `AccountDeleted`, remove the files | |
| 24 | `FailedUploadCleanedUp` | `CleanFailedUpload` | | P5 whenever `ConversionFailed` is older than the keep time, remove its files | |
| 25 | `AccountDeleted` | `DeleteAccount` | Reader | | Account page |
