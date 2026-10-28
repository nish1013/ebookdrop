"""P1: the outbox poller that converts each received upload."""

import shutil
import tempfile
import uuid
from pathlib import Path

from ebookdrop.clock import Clock
from ebookdrop.conversion.port import BookFormat, Conversion, ConverterPort
from ebookdrop.library.domain import BookEvent
from ebookdrop.library.service import cover_key, original_key
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

        A crash after the start leaves the book Processing for the stuck check.
        """
        if not self._store.start_job(book_id, self._clock.now()):
            return
        with tempfile.TemporaryDirectory() as work:
            work_dir = Path(work)
            source = work_dir / "original"
            with (
                self._storage.open(original_key(book_id)) as stored,
                source.open("wb") as copy,
            ):
                shutil.copyfileobj(stored, copy)
            conversion = self._converter.convert(source, work_dir)
            self._store.record(
                book_id,
                [_CONVERTED[conversion.format], BookEvent.BOOK_DETAILS_EXTRACTED],
                self._clock.now(),
            )
            self.mark_ready(book_id, conversion)

    def mark_ready(self, book_id: uuid.UUID, conversion: Conversion) -> bool:
        """P3: store the converted files and record `BookReady` once (R13)."""
        with conversion.book.open("rb") as book:
            self._storage.save(f"books/{book_id}/book.{conversion.format}", book)
        if conversion.cover is not None:
            with conversion.cover.open("rb") as cover:
                self._storage.save(cover_key(book_id), cover)
        return self._store.mark_ready(
            book_id,
            conversion.format,
            conversion.title,
            conversion.author,
            conversion.cover is not None,
            self._clock.now(),
        )
