import pytest

from ebookdrop.identity.domain import Email, InvalidEmailError


def test_r1_email_drops_outer_spaces() -> None:
    assert Email.parse(" ANA@Example.com ").value == "ANA@Example.com"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ana",
        "ana@",
        "@example.com",
        "ana@example",
        "an a@example.com",
        "ana@@example.com",
        f"{'a' * 245}@example.com",
    ],
)
def test_email_with_a_wrong_shape_is_refused(raw: str) -> None:
    with pytest.raises(InvalidEmailError):
        Email.parse(raw)
