"""Identity rows in Postgres."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    MetaData,
    Table,
    Text,
    delete,
    func,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError

from ebookdrop.identity.domain import Email, EmailTakenError

EMAIL_KEY_INDEX = "accounts_email_key"

_metadata = MetaData()
_accounts = Table(
    "accounts",
    _metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("email", Text),
    Column("password_hash", Text),
    Column("created_at", DateTime(timezone=True)),
)
_sessions = Table(
    "sessions",
    _metadata,
    Column("token_hash", Text, primary_key=True),
    Column("account_id", UUID(as_uuid=True)),
    Column("started_at", DateTime(timezone=True)),
    Column("expires_at", DateTime(timezone=True)),
)
_failures = Table(
    "sign_in_failures",
    _metadata,
    Column("email_key", Text),
    Column("at", DateTime(timezone=True)),
)
_email_key = func.lower(func.trim(_accounts.c.email))


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
        """Insert an account. Raise `EmailTakenError` when the unique key refuses it."""
        account_id = uuid.uuid4()
        row = {
            "id": account_id,
            "email": email.value,
            "password_hash": password_hash,
            "created_at": now,
        }
        try:
            with self._engine.begin() as connection:
                connection.execute(insert(_accounts), row)
        except IntegrityError as err:
            if _constraint(err) == EMAIL_KEY_INDEX:
                raise EmailTakenError from err
            raise
        return account_id

    def find_account(self, email: Email) -> AccountRow | None:
        """Return the account with this email key, or `None`."""
        query = select(_accounts.c.id, _accounts.c.email, _accounts.c.password_hash)
        with self._engine.connect() as connection:
            row = connection.execute(query.where(_email_key == email.key)).first()
        return AccountRow(row.id, row.email, row.password_hash) if row else None

    def start_session(
        self,
        token_hash: str,
        account_id: uuid.UUID,
        now: datetime,
        expires_at: datetime,
    ) -> None:
        """Store a session for the account."""
        row = {
            "token_hash": token_hash,
            "account_id": account_id,
            "started_at": now,
            "expires_at": expires_at,
        }
        with self._engine.begin() as connection:
            connection.execute(insert(_sessions), row)

    def find_session_email(self, token_hash: str, now: datetime) -> str | None:
        """Return the email of a live session, or `None`."""
        query = (
            select(_accounts.c.email)
            .join(_sessions, _sessions.c.account_id == _accounts.c.id)
            .where(_sessions.c.token_hash == token_hash, _sessions.c.expires_at > now)
        )
        with self._engine.connect() as connection:
            return connection.execute(query).scalar()

    def end_session(self, token_hash: str) -> None:
        """Remove the session. A missing session is not an error."""
        with self._engine.begin() as connection:
            connection.execute(
                delete(_sessions).where(_sessions.c.token_hash == token_hash)
            )

    def record_failure(self, email: Email, at: datetime) -> None:
        """Store one failed sign-in for the email key."""
        with self._engine.begin() as connection:
            connection.execute(insert(_failures), {"email_key": email.key, "at": at})

    def count_failures(self, email: Email, since: datetime) -> int:
        """Count failed sign-ins for the email key after `since`."""
        query = select(func.count()).where(
            _failures.c.email_key == email.key, _failures.c.at > since
        )
        with self._engine.connect() as connection:
            return connection.execute(query).scalar_one()


def _constraint(err: IntegrityError) -> str | None:
    diag = getattr(err.orig, "diag", None)
    return getattr(diag, "constraint_name", None)
