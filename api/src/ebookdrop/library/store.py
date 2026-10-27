"""Library rows in Postgres."""

from sqlalchemy import Engine


class LibraryStore:
    """Reads and writes books, conversion jobs and book events."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
