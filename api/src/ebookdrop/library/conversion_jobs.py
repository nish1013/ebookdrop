"""P1: the outbox poller that converts each received upload."""

import uuid

from ebookdrop.clock import Clock
from ebookdrop.conversion.port import ConverterPort
from ebookdrop.library.service import LibraryService
from ebookdrop.library.store import LibraryStore
from ebookdrop.storage import StoragePort


class ConversionJobs:
    """Takes conversion jobs from the outbox and runs them."""

    def __init__(
        self,
        store: LibraryStore,
        storage: StoragePort,
        converter: ConverterPort,
        library: LibraryService,
        clock: Clock,
    ) -> None:
        self._store = store
        self._storage = storage
        self._converter = converter
        self._library = library
        self._clock = clock

    def poll(self, limit: int = 10) -> int:
        """Run up to `limit` waiting jobs. Return how many were taken."""
        raise NotImplementedError

    def run(self, book_id: uuid.UUID) -> None:
        """Convert one upload, once per upload id, then call P3."""
        raise NotImplementedError
