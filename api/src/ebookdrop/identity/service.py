"""Identity commands: sign up, sign in, sign out, and the signed-in reader."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from ebookdrop.clock import Clock
from ebookdrop.identity.domain import (
    SESSION_LENGTH,
    SIGN_IN_FAILURE_LIMIT,
    SIGN_IN_FAILURE_WINDOW,
    Email,
    InvalidEmailError,
    SignedInReader,
    TooManyAttemptsError,
    WrongEmailOrPasswordError,
)
from ebookdrop.identity.store import IdentityStore

_hasher = PasswordHasher()
# An unknown email still pays for one hash check, so the answer time shows nothing.
_UNKNOWN_EMAIL_HASH = _hasher.hash(secrets.token_hex(16))


class IdentityService:
    """Runs the identity commands on one store and one clock."""

    def __init__(self, store: IdentityStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def sign_up(self, raw_email: str, password: str) -> Email:
        """Add an account. Raise `InvalidEmailError` or `EmailTakenError`."""
        email = Email.parse(raw_email)
        self._store.add_account(email, _hasher.hash(password))
        return email

    def sign_in(self, raw_email: str, password: str) -> str:
        """Start a session and return its token.

        Raise `TooManyAttemptsError` or `WrongEmailOrPasswordError`.
        """
        try:
            email = Email.parse(raw_email)
        except InvalidEmailError as err:
            raise WrongEmailOrPasswordError from err
        now = self._clock.now()
        failures = self._store.count_failures(email, since=now - SIGN_IN_FAILURE_WINDOW)
        if failures >= SIGN_IN_FAILURE_LIMIT:
            raise TooManyAttemptsError
        account = self._store.find_account(email)
        try:
            _hasher.verify(
                account.password_hash if account else _UNKNOWN_EMAIL_HASH, password
            )
        except VerifyMismatchError as err:
            self._store.record_failure(email, now)
            raise WrongEmailOrPasswordError from err
        if account is None:  # the password matched the random dummy hash
            raise WrongEmailOrPasswordError
        token = secrets.token_urlsafe(32)
        self._store.start_session(_digest(token), account.id, now + SESSION_LENGTH)
        return token

    def sign_out(self, token: str) -> None:
        """End the session of the token."""
        self._store.end_session(_digest(token))

    def delete_account(self, reader: SignedInReader) -> None:
        """`DeleteAccount`: sign-in stops at once. P6 removes the library later."""
        self._store.delete_account(reader.id, self._clock.now())

    def signed_in(self, token: str) -> SignedInReader | None:
        """Return the reader of the token's live session, or `None`."""
        return self._store.find_session_reader(_digest(token), self._clock.now())


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
