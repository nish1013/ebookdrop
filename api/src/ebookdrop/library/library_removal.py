"""P6 removes the library rows of a deleted account."""

import logging

from sqlalchemy.exc import SQLAlchemyError

from ebookdrop.clock import Clock
from ebookdrop.library.store import LibraryStore

_log = logging.getLogger(__name__)


class LibraryRemoval:
    """Removes the library of each deleted account, and queues P4 for its files."""

    def __init__(self, store: LibraryStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def poll(self, limit: int = 10) -> int:
        """P6: remove the libraries of up to `limit` deleted accounts.

        A removal that fails stays queued for the next poll, so one reader stops
        neither the others nor the later steps of the tick. Return how many.
        """
        done = 0
        for reader_id in self._store.deleted_accounts(limit):
            try:
                done += self._store.remove_library(reader_id, self._clock.now())
            except SQLAlchemyError:
                _log.warning(
                    "library removal failed",
                    exc_info=True,
                    extra={"reader_id": reader_id},
                )
        return done
