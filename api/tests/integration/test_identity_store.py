import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from ebookdrop.identity.domain import Email, EmailTakenError, SignedInReader
from ebookdrop.identity.store import IdentityStore

NOW = datetime(2026, 10, 27, 9, 0, tzinfo=UTC)


def test_r1_guard_refuses_a_second_row_for_one_email_key(engine: Engine) -> None:
    insert = text(
        "INSERT INTO accounts (id, email, password_hash) VALUES (:id, :email, 'h')"
    )
    with engine.begin() as connection:
        connection.execute(insert, {"id": uuid.uuid4(), "email": "ana@example.com"})

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert, {"id": uuid.uuid4(), "email": " ANA@example.com"})


def test_r1_store_reports_a_taken_email(engine: Engine) -> None:
    store = IdentityStore(engine)
    store.add_account(Email.parse("ana@example.com"), "h")

    with pytest.raises(EmailTakenError):
        store.add_account(Email.parse(" ANA@example.com"), "h")


def test_account_is_found_by_its_email_key(engine: Engine) -> None:
    store = IdentityStore(engine)
    account_id = store.add_account(Email.parse("Ana@example.com"), "h")

    account = store.find_account(Email.parse("ana@EXAMPLE.com"))

    assert account is not None
    assert (account.id, account.password_hash) == (account_id, "h")
    assert store.find_account(Email.parse("ben@example.com")) is None


def test_session_is_found_until_it_expires_or_ends(engine: Engine) -> None:
    store = IdentityStore(engine)
    account_id = store.add_account(Email.parse("ana@example.com"), "h")
    store.start_session("t1", account_id, NOW + timedelta(days=14))

    assert store.find_session_reader("t1", NOW) == SignedInReader(
        account_id, "ana@example.com"
    )
    assert store.find_session_reader("t1", NOW + timedelta(days=14)) is None

    store.end_session("t1")
    assert store.find_session_reader("t1", NOW) is None


def test_failures_count_inside_the_window_only(engine: Engine) -> None:
    store = IdentityStore(engine)
    ana = Email.parse("ana@example.com")
    store.record_failure(ana, NOW - timedelta(minutes=61))
    store.record_failure(ana, NOW - timedelta(minutes=30))
    store.record_failure(Email.parse("ben@example.com"), NOW)

    assert store.count_failures(ana, since=NOW - timedelta(hours=1)) == 1


def test_r1_lookup_uses_the_same_email_key_as_the_unique_index(engine: Engine) -> None:
    store = IdentityStore(engine)
    store.add_account(Email.parse("İnci@example.com"), "h")

    assert store.find_account(Email.parse("İnci@example.com")) is not None


def test_failures_count_with_the_same_email_key_as_the_unique_index(
    engine: Engine,
) -> None:
    store = IdentityStore(engine)
    store.record_failure(Email.parse("İnci@example.com"), NOW)

    assert (
        store.count_failures(
            Email.parse(" İNCİ@example.com"), since=NOW - timedelta(hours=1)
        )
        == 1
    )


def test_a_new_failure_removes_failures_older_than_the_window(engine: Engine) -> None:
    store = IdentityStore(engine)
    ana = Email.parse("ana@example.com")
    store.record_failure(ana, NOW - timedelta(hours=2))

    store.record_failure(ana, NOW)

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT count(*) FROM sign_in_failures")
        ).scalar()
    assert rows == 1
