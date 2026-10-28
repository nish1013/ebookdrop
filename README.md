# ebookdrop

A reader uploads an EPUB or PDF file. A Docker sandbox converts it, and the book appears in the reader's web library.

![The library with four converted books and one failed upload](docs/screenshots/library.png)

| Read a book in the browser | Upload the same file twice |
|---|---|
| ![The reader on chapter 1 of Pride and Prejudice](docs/screenshots/reader.png) | ![The upload form links to the book that is already there](docs/screenshots/upload-duplicate.png) |

| Sign up |
|---|
| ![The sign-up form](docs/screenshots/sign-up.png) |

The books in the screenshots are public-domain texts with generated covers.

```
browser ──> web (React, Vite) ──/api──> API (FastAPI) ──> PostgreSQL
                                          │                  ▲
                                          ▼                  │
                                   storage (disk) <── worker (outbox poller, crons)
                                                             │
                                                             ▼
                                              sandbox container per file (Docker)
```

## What it does

Release 1 has sign-up, upload, the library list, a browser reader, and book and account delete.

| Rule | Value |
|---|---|
| File types | EPUB and PDF. The API checks the type by content, not by extension. |
| File size | Max 50 MiB per file. |
| Library size | Max 1 GiB per reader. |
| Same file twice | The second upload gets a link to the first book. |
| Conversion | EPUB is normalised by Calibre. PDF stays as it is. Page 1 must render. |
| Stuck book | A book still Processing after 5 minutes fails as `stuck`. |
| Sandbox | One container per file: no network, read-only root, 512 MB, 64 pids, no log. |

The decisions are in `docs/decisions.md`. The changes from the plan are in `docs/plan-deviations.md`.

## Requirements

| Tool | Version |
|---|---|
| Python | 3.12 |
| uv | any recent |
| Node.js | 24 |
| Docker | a running daemon. The sandbox image is about 2 GB. |

## Run it on your machine

This starts a fresh PostgreSQL in Docker, the API and the worker on port 8000, and the web page on port 5173. The data goes when you stop it.

```
make install
make sandbox-image
cd api && uv run python scripts/serve_e2e.py
```

In a second terminal:

```
cd web && npm run dev
```

Then open `http://localhost:5173`.

## Run it on your own database

Each process reads its settings from the environment.

| Variable | Read by | Value |
|---|---|---|
| `DATABASE_URL` | API, worker, migrations, metrics | A SQLAlchemy URL, for example `postgresql+psycopg://user:pass@host/ebookdrop`. |
| `STORAGE_DIR` | API, worker | A folder that the API and the worker both write. |
| `APP_ORIGIN` | API | The origin of the web page, for example `https://ebookdrop.example`. |

The API refuses a POST, PUT or DELETE whose `Origin` is not `APP_ORIGIN`, with 403 `cross_origin`.

```
cd api && uv run alembic upgrade head
cd api && uv run uvicorn ebookdrop.app:app_from_env --factory --port 8000
cd api && uv run python -m ebookdrop.worker
```

Run the API and the worker as two processes. The worker needs Docker and the `ebookdrop-sandbox` image.

## Commands

| Command | Does |
|---|---|
| `make install` | Installs the API and web packages and the Playwright browser. |
| `make sandbox-image` | Builds the `ebookdrop-sandbox` image. |
| `make lint` | Runs ruff, mypy, eslint and tsc. Fails when the API types are out of date. |
| `make test` | Runs the API tests, then the browser tests. CI runs the same. |
| `make metrics` | Prints the daily share of books ready within 2 minutes, late books, open failures and rejects. |
| `make api-types` | Rebuilds `api/openapi.json` and `web/src/api/schema.d.ts`. |

The tests need Docker. They start PostgreSQL with Testcontainers and build the sandbox test images.
