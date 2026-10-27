import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from ebookdrop.identity.domain import Email, EmailTakenError
from ebookdrop.identity.store import IdentityStore

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def test_r1_guard_refuses_a_second_row_for_one_email_key(engine: Engine) -> None:
    insert = text(
        "INSERT INTO accounts (id, email, password_hash, created_at)"
        " VALUES (:id, :email, 'h', now())"
    )
    with engine.begin() as connection:
        connection.execute(insert, {"id": uuid.uuid4(), "email": "ana@example.com"})

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert, {"id": uuid.uuid4(), "email": " ANA@example.com"})


def test_r1_store_reports_a_taken_email(engine: Engine) -> None:
    store = IdentityStore(engine)
    store.add_account(Email.parse("ana@example.com"), "h", NOW)

    with pytest.raises(EmailTakenError):
        store.add_account(Email.parse(" ANA@example.com"), "h", NOW)


def test_account_is_found_by_its_email_key(engine: Engine) -> None:
    store = IdentityStore(engine)
    account_id = store.add_account(Email.parse("Ana@example.com"), "h", NOW)

    account = store.find_account(Email.parse("ana@EXAMPLE.com"))

    assert account is not None
    assert (account.id, account.email, account.password_hash) == (
        account_id,
        "Ana@example.com",
        "h",
    )
    assert store.find_account(Email.parse("ben@example.com")) is None


def test_session_is_found_until_it_expires_or_ends(engine: Engine) -> None:
    store = IdentityStore(engine)
    account_id = store.add_account(Email.parse("ana@example.com"), "h", NOW)
    store.start_session("t1", account_id, NOW, NOW + timedelta(days=14))

    assert store.find_session_email("t1", NOW) == "ana@example.com"
    assert store.find_session_email("t1", NOW + timedelta(days=14)) is None

    store.end_session("t1")
    assert store.find_session_email("t1", NOW) is None


def test_failures_count_inside_the_window_only(engine: Engine) -> None:
    store = IdentityStore(engine)
    ana = Email.parse("ana@example.com")
    store.record_failure(ana, NOW - timedelta(minutes=61))
    store.record_failure(ana, NOW - timedelta(minutes=30))
    store.record_failure(Email.parse("ben@example.com"), NOW)

    assert store.count_failures(ana, since=NOW - timedelta(hours=1)) == 1
