import pytest
from cryptography.fernet import Fernet

from app.db.errors import DatabaseUnavailableError
from app.security.crypto import FieldCipher
from app.security.passwords import hash_password, password_level, verify_password

# Os mesmos casos existem em apps/web/src/auth/passwordStrength.test.ts.
LEVELS = [
    ("", 0),
    ("abc", 0),
    ("1234567", 0),
    ("password", 0),
    ("aaaaaaaaaaaa", 0),
    ("abcdefgh", 1),
    ("abcdefg1", 1),
    ("Abcdefg1", 2),
    ("abcdefghijkl", 2),
    ("Abcdefghij1k", 3),
    ("abcdefghijklmnop", 3),
    ("Abcdefghijklmn1!", 4),
]


@pytest.mark.parametrize(("password", "level"), LEVELS)
def test_password_level(password: str, level: int) -> None:
    assert password_level(password) == level


def test_hash_password_is_salted_and_verifiable() -> None:
    first = hash_password("Abcdefg1!")
    second = hash_password("Abcdefg1!")

    assert first != second
    assert first.startswith("scrypt$")
    assert "Abcdefg1!" not in first
    assert verify_password("Abcdefg1!", first)
    assert not verify_password("Abcdefg1?", first)


@pytest.mark.parametrize("stored", ["", "x", "bcrypt$1$2$3$4$5", "scrypt$a$b$c$d$e"])
def test_verify_password_rejects_malformed_hashes(stored: str) -> None:
    assert not verify_password("Abcdefg1!", stored)


def test_cipher_round_trip_and_blind_index() -> None:
    cipher = FieldCipher(Fernet.generate_key().decode())

    token = cipher.encrypt("Ana Silva")

    assert token != "Ana Silva"
    assert cipher.encrypt("Ana Silva") != token  # IV aleatório
    assert cipher.decrypt(token) == "Ana Silva"
    assert cipher.blind_index("a@b.pt") == cipher.blind_index("a@b.pt")
    assert cipher.blind_index("a@b.pt") != cipher.blind_index("c@b.pt")


def test_cipher_with_other_key_cannot_decrypt() -> None:
    token = FieldCipher(Fernet.generate_key().decode()).encrypt("segredo")

    with pytest.raises(ValueError, match="inválido"):
        FieldCipher(Fernet.generate_key().decode()).decrypt(token)


@pytest.mark.parametrize("key", ["", "curta", "A" * 44])
def test_cipher_rejects_invalid_keys(key: str) -> None:
    with pytest.raises(DatabaseUnavailableError):
        FieldCipher(key)
