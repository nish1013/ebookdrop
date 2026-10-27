# Aggregates

Commands: [commands.md](commands.md). An aggregate takes a command, checks its rule, and
emits the event. Step ④: the rule of each command, the data it reads, the guard.

## Rule per command

| Command | Rule | When | Data the rule reads | Aggregate |
|---|---|---|---|---|
| `SignUp` | R1 One email has one account. | before the event: immediate | All accounts, by `lower(trim(email))` | None: a set rule, a unique key |
| `SignIn`, `SignOut` | None on stored data. | | | None: plain data |
| `UploadBook` | R6 One book per (reader, sha256). | immediate | Ana's books, by sha256 | `Library(reader)` |
| `UploadBook` | R10 Ana's files total 1 GB or less. | immediate | Ana's bytes used | `Library(reader)` |
| `ConvertBook` | One conversion per upload. | | One job, by upload id | None: an idempotency key on P1 |
| `MarkBookReady` | R13 A book leaves Processing once. A deleted book never comes back. | immediate | One book row of Ana | `Library(reader)` |
| `FailStuckConversion` | R13 | immediate | One book row of Ana | `Library(reader)` |
| `OpenBook` | R2 of S1: only the owner. | | | None: a criterion, the owner filter |
| `DeleteBook` | R13, and the bytes used go down. | immediate | One book row, Ana's bytes used | `Library(reader)` |
| `RemoveBookFiles`, `CleanFailedUpload` | Removal runs twice with the same result. | | Storage keys of one book | None: idempotent by storage key |
| `DeleteAccount` | A deleted account cannot sign in. | immediate | One account row | `Account(reader)` |
| `DeleteAccount` | The library of a deleted account goes. | after the event: eventual | Ana's books | Policy P6 |

## Aggregates

### Library(reader)

```
Command   UploadBook, MarkBookReady, FailStuckConversion, DeleteBook
Rules     R6 one book per (reader, sha256)                  immediate
          R10 bytes used ≤ 1 GiB                            immediate
          R13 Processing -> Ready or Failed, once. Deleted is final.   immediate
Reads     Ana's books and Ana's bytes used                  one reader, never two
Holds     libraries(reader_id PK, bytes_used)  ·  books(id, reader_id, sha256, size, status, ...)
Guard     unique (reader_id, sha256)
          CHECK (bytes_used <= 1073741824), changed only by
            UPDATE libraries SET bytes_used = bytes_used + :size
            WHERE reader_id = :r AND bytes_used + :size <= 1073741824
          UPDATE books SET status = 'ready' WHERE id = :id AND status = 'processing'
            0 rows: no event (deleted, already ready, or already failed)
```

| Why one aggregate | |
|---|---|
| R6 and R10 read the same scope: one reader's books. | Both rules read the same rows, so they merge. |
| `DeleteBook` changes the book and the bytes used. | Two aggregates would break "one command, one aggregate". |
| A reader rarely uploads two files at once. | One lock per reader blocks nobody else. |

### Account(reader)

```
Command   SignUp, DeleteAccount
Rule      R1 one email, one account                 a set rule
          a deleted account cannot sign in          immediate
Reads     one account row
Guard     unique index on lower(trim(email))
          sessions.reader_id references accounts ON DELETE CASCADE
```

## Policies

| P | Whenever | Then | From | To |
|---|---|---|---|---|
| P1 | `UploadReceived` | `ConvertBook` | `Library(reader)` | Conversion tool |
| P2 | `ProcessingDeadlinePassed` | `FailStuckConversion` | Clock | `Library(reader)` |
| P3 | `EpubNormalised` or `PdfKeptAsIs` | `MarkBookReady` | Conversion tool | `Library(reader)` |
| P4 | `BookDeleted`, `BookDeletedDuringConversion` or `AccountDeleted` | `RemoveBookFiles` | `Library(reader)` | Storage |
| P5 | `ConversionFailed` older than 7 days | `CleanFailedUpload` | Clock | Storage |
| P6 | `AccountDeleted` | Remove the library rows | `Account(reader)` | `Library(reader)` |

Step ⑤ picks a strategy for each policy.

## Values

| Value object | Rule at creation |
|---|---|
| `Sha256` | 64 lowercase hex characters |
| `FileSize` | 1 byte to 52428800 bytes (50 MiB) |
| `BookFormat` | `epub` or `pdf`, from the content |
| `Email` | Trimmed, lowercase for compare |

## Two requests at once

| Rule | Race | Guard | Test that fails when the guard goes |
|---|---|---|---|
| R1 | Two sign-ups with one email | Unique index | S1 AC3 |
| R6 | A double click on Upload | Unique (reader_id, sha256) | S4 AC6, twice in parallel |
| R10 | Two 30 MB uploads at 980 MB | Conditional update on `bytes_used` | S4 AC10 |
| R13 | `MarkBookReady`, `FailStuckConversion` and `DeleteBook` on one book | Conditional update on `status` | S6 AC4, S7 AC2 |

## Contexts

Step ⑤. The aggregates confirm two contexts. Conversion is a tool behind a port.

```
+-----------------------+   who is signed in (ask)   +---------------------------------+
| Identity              |<---------------------------| Library                         |
| Account(reader)       |                            | Library(reader)                 |
| SignUp SignIn         |--- P6 AccountDeleted ----->| UploadBook MarkBookReady        |
| SignOut DeleteAccount |                            | FailStuckConversion DeleteBook  |
+-----------------------+                            | views: list, reader view,       |
                                                     | metric report                   |
                                                     +---------------------------------+
                                                       │ P1 ConvertBook    ▲ P3 MarkBookReady
                                                       ▼                   │
                                                     [ ConverterPort ] -> sandbox tool
                                                       │ P4 P5
                                                       ▼
                                                     [ StoragePort ] -> file store
```

| Draft | Confirmed | Why |
|---|---|---|
| Identity | Identity | `Account(reader)` owns R1 and sign-in. |
| Library | Library | `Library(reader)` owns R6, R10, R13. It owns the book status (Q14). |
| Conversion context | A tool behind `ConverterPort` | No aggregate. Its one rule is an idempotency key. |
| Reading context | A view in Library | `OpenBook` reads. It decides nothing. |
| Metrics | A view in Library | `BookReadyLate` is derived from events 7 and 16. |

## Policy strategies

| P | Strategy | Why |
|---|---|---|
| P1 | Outbox row in the `UploadReceived` transaction, polled by the same service | One service, one database. A crash after the commit loses nothing (Q11). |
| P2 | Cron every minute: Processing books older than the deadline | Lag of one minute is fine. It also catches a crash after conversion. |
| P3 | In-process: the conversion job calls `MarkBookReady` when the tool returns | Same service. A crash before the call is caught by P2. |
| P4 | Outbox row in the delete transaction, polled, retried until done | Removal is idempotent by storage key (Q16). |
| P5 | Cron once a day | Days of lag are fine. |
| P6 | Outbox row in the `AccountDeleted` transaction, polled | Decision 18: seconds of lag are fine. |

## Checks

| Check | Result | Note |
|---|---|---|
| Every event has a command or a policy | Pass, 2 exceptions | `ProcessingDeadlinePassed` is time. `BookReadyLate` is derived on read. |
| Every command has an role or a policy | Pass | S5, S6, S7, S10, S11 run from P1 to P5. P6 has no command name. It removes rows only. |
| Every word comes from the timeline | Pass | Reject and failure reasons are on the timeline, events 5 and 13. |
| One command changes one aggregate | Pass | `DeleteAccount` changes `Account(reader)` only (decision 18). |
| Each fact lives in one place | Pass, 1 copy | `libraries.bytes_used` copies the sum of `books.size`. Reason: the quota guard needs one row to update. |
| Each policy names its strategy | Pass | Policy strategies table. |
| Each arrow between contexts is ask | Pass | Library asks Identity for the signed-in reader. P6 carries an event, by outbox. |
