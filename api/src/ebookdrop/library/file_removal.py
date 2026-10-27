"""P4 removes the files of a deleted book. P5 removes the files of a failed upload."""

import logging

from ebookdrop.clock import Clock
from ebookdrop.library.domain import FAILED_KEEP, STAGING_KEEP, BookEvent
from ebookdrop.library.service import STAGING, stored_keys
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import StoragePort

_log = logging.getLogger(__name__)


class FileRemoval:
    """Removes stored files that no book needs any more.

    Each removal runs again with the same result: a missing file is no error.
    """

    def __init__(self, store: LibraryStore, storage: StoragePort, clock: Clock) -> None:
        self._store = store
        self._storage = storage
        self._clock = clock

    def poll(self, limit: int = 10) -> int:
        """P4: remove the files of up to `limit` deleted books. Return how many.

        A removal that fails stays queued for the next poll.
        """
        done = 0
        for removal in self._store.waiting_removals(limit):
            try:
                for key in stored_keys(removal.book_id, removal.format):
                    self._storage.delete(key)
            except OSError:
                _log.exception(
                    "file removal failed", extra={"book_id": removal.book_id}
                )
                continue
            done += self._store.finish_removal(removal.book_id, self._clock.now())
        return done

    def clean_failed(self) -> int:
        """P5: remove the files of each upload that failed `FAILED_KEEP` ago.

        The Failed row stays. Return how many uploads lost their files.
        """
        now = self._clock.now()
        failed = self._store.failed_to_clean(now - FAILED_KEEP)
        for book_id in failed:
            for key in stored_keys(book_id, None):
                self._storage.delete(key)
            self._store.record(book_id, [BookEvent.FAILED_UPLOAD_CLEANED_UP], now)
        return len(failed)

    def sweep_staging(self) -> int:
        """Remove each staging file older than `STAGING_KEEP` (decision 23).

        Return how many files went.
        """
        stale_by = self._clock.now() - STAGING_KEEP
        stale = [f for f in self._storage.files(STAGING) if f.modified_at < stale_by]
        for stored in stale:
            self._storage.delete(stored.key)
        return len(stale)
