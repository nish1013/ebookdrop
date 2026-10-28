"""P1: the outbox poller that converts each received upload."""

import shutil
import tempfile
import uuid
from pathlib import Path

from ebookdrop.clock import Clock
from ebookdrop.conversion.port import (
    BookFormat,
    Conversion,
    ConversionFailedError,
    ConverterPort,
    SandboxEscapeError,
)
from ebookdrop.library.domain import STUCK_AFTER, BookDetails, BookEvent, FileName
from ebookdrop.library.service import (
    book_key,
    cover_key,
    original_key,
    staging_key,
)
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import StoragePort

_CONVERTED = {
    BookFormat.EPUB: BookEvent.EPUB_NORMALISED,
    BookFormat.PDF: BookEvent.PDF_KEPT_AS_IS,
}


class ConversionJobs:
    """Takes conversion jobs from the outbox and runs them."""

    def __init__(
        self,
        store: LibraryStore,
        storage: StoragePort,
        converter: ConverterPort,
        clock: Clock,
    ) -> None:
        self._store = store
        self._storage = storage
        self._converter = converter
        self._clock = clock

    def poll(self, limit: int = 10) -> int:
        """Run up to `limit` waiting jobs. Return how many were taken."""
        waiting = self._store.waiting_jobs(limit)
        for book_id in waiting:
            self.run(book_id)
        return len(waiting)

    def run(self, book_id: uuid.UUID) -> None:
        """Convert one upload, once per upload id, then call P3.

        A failed conversion fails the book. A crash after the start, or a sandbox
        that does not run, leaves the book Processing for the stuck check.
        """
        name = self._store.start_job(book_id, self._clock.now())
        if name is None:
            return
        with tempfile.TemporaryDirectory() as work:
            work_dir = Path(work)
            source = work_dir / "original"
            with (
                self._storage.open(original_key(book_id)) as stored,
                source.open("wb") as copy,
            ):
                shutil.copyfileobj(stored, copy)
            try:
                conversion = self._converter.convert(source, work_dir)
            except ConversionFailedError as failed:
                self.fail(book_id, failed)
                return
            self._store.record(
                book_id,
                [_CONVERTED[conversion.format], BookEvent.BOOK_DETAILS_EXTRACTED],
                self._clock.now(),
            )
            self.mark_ready(book_id, conversion, name)

    def mark_ready(
        self, book_id: uuid.UUID, conversion: Conversion, name: FileName
    ) -> bool:
        """P3: record `BookReady` once (R13), and move the files to the book key.

        The converted files wait in `staging/<upload id>/` until the update.
        With no update, the staging files go (decision 23). A failure after the
        move also removes the moved files, so a Processing book has none. A
        missing title or author gets its fallback (decision 11).
        """
        files = {book_key(book_id, conversion.format): conversion.book}
        if conversion.cover is not None:
            files[cover_key(book_id)] = conversion.cover
        moved: list[str] = []

        def move() -> None:
            for key in files:
                self._storage.move(staging_key(book_id, key), key)
                moved.append(key)

        ready = False
        try:
            for key, path in files.items():
                with path.open("rb") as converted:
                    self._storage.save(staging_key(book_id, key), converted)
            details = BookDetails.extracted(conversion.title, conversion.author, name)
            ready = self._store.mark_ready(
                book_id,
                conversion.format,
                details,
                conversion.cover is not None,
                self._clock.now(),
                move,
            )
        finally:
            if not ready:
                for key in files:
                    self._storage.delete(staging_key(book_id, key))
                for key in moved:
                    self._storage.delete(key)
        return ready

    def fail_stuck(self) -> int:
        """P2: fail each book still Processing at its deadline. Return how many."""
        now = self._clock.now()
        return self._store.fail_stuck(now - STUCK_AFTER, now)

    def fail(self, book_id: uuid.UUID, failed: ConversionFailedError) -> bool:
        """Record `ConversionFailed(reason)` once (R13), after an escape its block."""
        escape = isinstance(failed, SandboxEscapeError)
        return self._store.fail(book_id, failed.failure, escape, self._clock.now())
