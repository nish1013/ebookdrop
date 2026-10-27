"""P4 removes the files of a deleted book. P5 removes the files of a failed upload."""

from ebookdrop.clock import Clock
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import StoragePort


class FileRemoval:
    """Removes stored files that no book needs any more."""

    def __init__(self, store: LibraryStore, storage: StoragePort, clock: Clock) -> None:
        self._store = store
        self._storage = storage
        self._clock = clock

    def poll(self, limit: int = 10) -> int:
        """P4: remove the files of up to `limit` deleted books."""
        return 0

    def clean_failed(self) -> int:
        """P5: remove the files of each upload that failed `FAILED_KEEP` ago."""
        return 0

    def sweep_staging(self) -> int:
        """Remove the staging files older than `STAGING_KEEP` (decision 23)."""
        return 0
