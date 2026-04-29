"""v0.4.2: UserManager pluggable backends + API-key flow."""

from __future__ import annotations

import pytest

from neuromem.user import UserManager
from neuromem.user_store import (
    InMemoryUserStore,
    SqlUserStore,
    generate_api_key,
    hash_api_key,
    verify_api_key,
)


@pytest.fixture(autouse=True)
def _isolate_user_manager():
    UserManager.reset()
    yield
    UserManager.reset()


def test_classmethod_api_preserved_for_v041_callers() -> None:
    u = UserManager.create(external_id="alice@example.com", metadata={"role": "dev"})
    assert UserManager.get(u.id).external_id == "alice@example.com"
    assert UserManager.get_by_external_id("alice@example.com").id == u.id
    assert UserManager.update_metadata(u.id, {"team": "platform"}) is True
    assert UserManager.list_all()[0].metadata["team"] == "platform"
    assert UserManager.delete(u.id) is True
    assert UserManager.get(u.id) is None


def test_create_with_api_key_returns_one_time_plaintext() -> None:
    user, plain = UserManager.create_with_api_key(external_id="svc@example.com")
    assert plain.startswith("nm_")
    assert user.api_key_hash != plain
    found = UserManager.get_by_api_key(plain)
    assert found is not None and found.id == user.id
    assert UserManager.get_by_api_key("wrong-key") is None


def test_sql_user_store_persists_across_manager_resets() -> None:
    store = SqlUserStore("sqlite:///:memory:")
    UserManager.configure(store)
    user, plain = UserManager.create_with_api_key(external_id="persist@example.com")
    user_id = user.id

    UserManager.reset()  # would wipe in-memory
    UserManager.configure(store)  # but store has the row

    assert UserManager.get(user_id).external_id == "persist@example.com"
    assert UserManager.get_by_api_key(plain).id == user_id


def test_bcrypt_hash_is_one_way_and_verifiable() -> None:
    plain = generate_api_key()
    hashed = hash_api_key(plain)
    assert hashed != plain
    assert verify_api_key(plain, hashed) is True
    assert verify_api_key("not-the-key", hashed) is False
