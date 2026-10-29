# Progress

**Status:** Release 1 is on `main`: sign-up to account delete, a styled web UI, README with screenshots, MIT licence. Updated 2026-10-29.

| Done | Where |
|---|---|
| Decision 33 cites no review label. | PR #18 |
| The web pages use shadcn/ui components on Tailwind CSS. The README opens with screenshots. | PR #17 |
| MIT licence. | PR #16 |
| README: what the app does, how to run it, the settings and the commands. | PR #15 |
| A reader deletes the account and the whole library. Changes from another origin get 403 `cross_origin`. | PR #14 |
| A reader deletes a book, and its files go. | PR #13 |
| Sandbox containers keep no log of the file output. | PR #12 |
| A reader reads a book in the browser, and no book script runs. | PR #11 |
| Stuck books fail after 5 minutes. The metric report. | PR #10 |
| The real converter runs in the sandbox, with a staging folder. | PR #9 |
| Size, type, DRM, password and quota checks run in a sandbox. | PR #8 |
| An upload reaches Ready with a stub converter. | PR #7 |
| A visitor signs up, signs in and signs out. A sign-in lasts 14 days. | PR #6 |

**In progress:** none.

**Next:** decide where the app runs (no deploy target exists). Each API deploy sets `APP_ORIGIN`.

**Open questions:** none. The ship decisions are decisions 30-34 in `docs/decisions.md`.

## Earlier

| Done | Where |
|---|---|
| Stage `mvp` and the sign-up reject event | PR #5 |
| Aggregate words and contexts | PR #4 |
| Event model and the locked plan of 8 PRs | PR #3 |
| Picture, example map and first design decisions | PR #2 |
| Brief and product decisions for file upload | PR #1 |
