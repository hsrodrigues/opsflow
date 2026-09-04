"""Tests for password hashing (seção 6/24)."""
from app.core.security import hash_password, needs_rehash, verify_password


def test_hash_password_never_returns_the_plaintext():
    hashed = hash_password("Sup3rSecret!")
    assert hashed != "Sup3rSecret!"
    assert hashed.startswith("$argon2")


def test_verify_password_accepts_the_correct_password():
    hashed = hash_password("Sup3rSecret!")
    assert verify_password("Sup3rSecret!", hashed) is True


def test_verify_password_rejects_a_wrong_password():
    hashed = hash_password("Sup3rSecret!")
    assert verify_password("wrong-password", hashed) is False


def test_needs_rehash_is_false_for_a_freshly_hashed_password():
    hashed = hash_password("Sup3rSecret!")
    assert needs_rehash(hashed) is False
