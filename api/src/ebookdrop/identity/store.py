"""Identity rows in Postgres."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine

from ebookdrop.identity.domain import Email


@dataclass(frozen=True)
class AccountRow:
    """One account as the store holds it."""

    id: uuid.UUID
    email: str
    password_hash: str


class IdentityStore:
    """Reads and writes accounts, sessions and failed sign-ins."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_account(self, email: Email, password_hash: str, now: datetime) -> uuid.UUID:
        raise NotImplementedError

    def find_account(self, email: Email) -> AccountRow | None:
        raise NotImplementedError

    def start_session(
        self,
        token_hash: str,
        account_id: uuid.UUID,
        now: datetime,
        expires_at: datetime,
    ) -> None:
        raise NotImplementedError

    def find_session_email(self, token_hash: str, now: datetime) -> str | None:
        raise NotImplementedError

    def end_session(self, token_hash: str) -> None:
        raise NotImplementedError

    def record_failure(self, email: Email, at: datetime) -> None:
        raise NotImplementedError

    def count_failures(self, email: Email, since: datetime) -> int:
        raise NotImplementedError
