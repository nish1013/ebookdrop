# Plan

Status: locked, 2026-10-27

Scope: release 1 of the brief, plus delete (decision 9). Model: [aggregates.md](aggregates.md).
Criteria: [commands.md](commands.md).

## Stack

| Layer | Pick | Why |
|---|---|---|
| API | Python 3.12, FastAPI, Pydantic | The file tools (pikepdf, Calibre) are Python. Typed request models. |
| Database | PostgreSQL 16, SQLAlchemy Core, Alembic | Unique keys, `CHECK` and conditional updates carry the guards. |
| Jobs | Outbox poller and crons in one worker process | One service, one database (policy strategies). |
| Sandbox | One Docker container per job: no network, read-only root, 512 MB, 64 pids | Every parse of an untrusted file runs here (decision 19). |
| File tools | pikepdf, Calibre `ebook-convert`, poppler `pdftoppm` | Inspect, normalise, render page 1 (decision 15). |
| Storage | Local disk behind `StoragePort`, areas `staging/` and `books/` | A playground. An S3 adapter fits the same port. |
| Web UI | React 18, TypeScript, Vite, React Router | Pages: sign-up, sign-in, library, reader, account. |
| Forms | React Hook Form with Zod | One schema per form, mirrored from the API models. |
| API client | Typed client generated from the OpenAPI schema | No hand-written request shapes. |
| Reader view | foliate-js for EPUB, pdf.js for PDF, in a sandboxed iframe | No book script runs (S8 AC4). |
| Tests | pytest, Testcontainers (Postgres), Vitest, Playwright | One command: `make test`. CI runs the same. |

## Endpoints

| Method and path | Command | Answers |
|---|---|---|
| `POST /api/accounts` | `SignUp` | 201, 409 email taken |
| `POST /api/sessions` | `SignIn` | 204 with cookie, 401, 429 too many attempts |
| `GET /api/sessions/current` | Signed-in reader | 200 with the email, 401 |
| `DELETE /api/sessions/current` | `SignOut` | 204 |
| `DELETE /api/accounts/me` | `DeleteAccount` | 204 |
| `POST /api/books` | `UploadBook` | 201 Processing, 409 duplicate, 413 too large, 422 reason |
| `GET /api/books` | Library list | 200 |
| `GET /api/books/{id}/content` | `OpenBook` | 200, 404 for a missing or foreign book |
| `DELETE /api/books/{id}` | `DeleteBook` | 204, 404 |

The metric report is a SQL view and `make metrics`. It has no endpoint.

## PR series

| PR | Delivers | Criteria | Proves | Risk |
|---|---|---|---|---|
| 1 | Skeleton, CI, sign-up, sign-in, sign-out | S1 AC1-AC3, S2 AC1-AC2, S3 AC1-AC2 | R1 guard | high: auth model, a sign-up race |
| 2 | Thin slice: upload to Ready, converter stub | S4 AC1, AC7, S5 AC1-AC2, AC7, S6 AC1-AC2 | P1, P3 | normal: stub only |
| 3 | Intake guards with the sandboxed inspect | S4 AC2-AC6, AC8-AC14 | R6, R10 guards | high: two races, untrusted parse |
| 4 | Real converter adapter, staging folder | S5 AC3-AC6, AC8 | Port contract test | high: untrusted parse |
| 5 | Stuck books and the metric report | S6 AC3, AC5, S7 AC1-AC2 | R13 against P2, P2 | normal: a cron |
| 6 | Read in the browser | S8 AC1-AC4 | Owner filter | high: book scripts, IDOR |
| 7 | Book delete and file removal | S6 AC4, S9 AC1-AC3, S10 AC1-AC2, S11 AC1 | R13 against delete, P4, P5 | high: cannot be undone |
| 8 | Account delete | S12 AC1-AC2 | P6 | high: cannot be undone |

Each criterion is in exactly one PR. A PR that adds a screen adds its Playwright spec.

## Tests

| Level | What | Rule |
|---|---|---|
| Unit | Value objects, aggregate rules | No database. |
| Integration | Each guard against Postgres | Each race test fails when its guard is removed. |
| Contract | `ConverterPort` | One suite runs against the stub and the real adapter. |
| Browser | One spec per screen | Runs in CI with `make test`. |

## Threat model

One row per entry point. The PR that adds the entry point holds its tests.

| Entry | Threat | Control | PR |
|---|---|---|---|
| `POST /api/accounts`, `/sessions` | Password guessing | Argon2id, 10 failed sign-ins per email per hour | 1 |
| Session cookie | Theft, CSRF | HttpOnly, Secure, SameSite=Lax, 14 days | 1 |
| `POST /api/books` | Zip bomb, parser exploit | 50 MiB stream limit, sandbox with no network, 10 s inspect | 3 |
| Converter | Escape, hang | Container limits, 60 s timeout, `SandboxEscapeBlocked` | 4 |
| `GET /api/books/{id}/content` | IDOR, script in a book | Owner filter, 404, sandboxed iframe, CSP `script-src 'none'` | 6 |
| Delete endpoints | Data left behind | P4 retries, staging sweep, a test per file kind | 7, 8 |

## Verify

```
make test        unit, integration, contract, browser
make lint        ruff, mypy, eslint, tsc
make metrics     daily share of books ready within 2 minutes
```

## Deviations

## D1. A read for the signed-in reader (PR 1, 2026-10-27)

**In short:** The web pages ask the server which reader is signed in.

- **Plan:** The endpoint table has no read for PR 1. `GET /api/books` comes in PR 2.
- **Built:** `GET /api/sessions/current` answers 200 with the email, or 401.
- **Why:** S2 AC1 and S3 AC1-AC2 need a signed-in check before PR 2. The library list belongs to PR 2.
- **Undo:** Remove the endpoint. The library page then calls `GET /api/books` for the same check.

## D2. Too many failed sign-ins answer 429 (PR 1, 2026-10-27)

**In short:** After 10 failed sign-ins for one email in one hour, sign-in stops for that email.

- **Plan:** The threat model sets the limit. The endpoint table lists 401 only for `SignIn`.
- **Built:** The 11th attempt gets 429 `too_many_attempts`, also with the right password.
- **Why:** A 401 at the limit hides the lock from the reader. The 429 code is the HTTP answer for a rate limit.
- **Undo:** Answer 401 at the limit. The count and the window stay.

## D3. Sign-up signs the reader in (PR 1, 2026-10-27)

**In short:** After sign-up, the page signs the reader in and shows the library.

- **Plan:** S1 AC1 says Ana has an empty library. The plan names no page flow.
- **Built:** The sign-up page calls `POST /api/accounts`, then `POST /api/sessions`.
- **Why:** The reader must see the library after sign-up. Two calls keep one command per endpoint.
- **Undo:** Send the reader to the sign-in page after sign-up.
