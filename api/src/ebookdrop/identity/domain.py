"""Identity values and rules."""

from dataclasses import dataclass

MAX_EMAIL_LENGTH = 254


class IdentityError(Exception):
    """Root of the identity errors."""


class InvalidEmailError(IdentityError):
    """The text is not an email address."""


@dataclass(frozen=True)
class Email:
    """An email address. Outer spaces do not count, and case does not count (R1)."""

    value: str
    key: str

    @classmethod
    def parse(cls, raw: str) -> "Email":
        """Trim the text and check its shape. Raise `InvalidEmailError` when wrong."""
        value = raw.strip()
        local, at, domain = value.partition("@")
        if (
            not at
            or not local
            or "@" in domain
            or "." not in domain.strip(".")
            or any(char.isspace() for char in value)
            or len(value) > MAX_EMAIL_LENGTH
        ):
            raise InvalidEmailError
        return cls(value, value.lower())


class EmailTakenError(IdentityError):
    """An account with this email exists (R1)."""
