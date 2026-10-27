"""Identity values and rules."""

from dataclasses import dataclass


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
        return cls(raw, raw)
