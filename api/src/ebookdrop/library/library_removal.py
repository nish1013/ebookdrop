"""P6 removes the library rows of a deleted account."""

from ebookdrop.clock import Clock
from ebookdrop.library.store import LibraryStore


class LibraryRemoval:
    """Removes the library of each deleted account, and queues P4 for its files."""

    def __init__(self, store: LibraryStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def poll(self, limit: int = 10) -> int:
        """P6: remove the libraries of up to `limit` deleted accounts.

        Return how many.
        """
        done = 0
        for reader_id in self._store.deleted_accounts(limit):
            done += self._store.remove_library(reader_id, self._clock.now())
        return done
