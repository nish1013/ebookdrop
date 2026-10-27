"""The check that runs inside the inspect container.

It reads one file from stdin and prints one verdict word. It imports no app code,
because the image holds this file only.
"""


def check(data: bytes) -> str:
    """Return `epub`, `pdf` or a refusal word for the bytes of one file."""
    raise NotImplementedError
