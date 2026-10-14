"""Hash de passwords (scrypt com sal) e medição da sua qualidade.

A qualidade (`password_level`, 0 a 4) tem de ficar igual à de
`apps/web/src/auth/passwordStrength.ts`:
- 0 `muito fraca`: menos de 8 caracteres ou uma password comum;
- caso contrário parte de 1 e soma 1 por cada: ≥ 12 caracteres, ≥ 16 caracteres,
  ≥ 3 classes de caracteres (minúsculas, maiúsculas, dígitos, símbolos).
"""

import base64
import hashlib
import hmac
import secrets

#: Nível mínimo aceite no registo (2 = razoável).
MIN_PASSWORD_LEVEL = 2
MAX_PASSWORD_LENGTH = 128

_SCRYPT_N_LOG2 = 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_SCRYPT_MAXMEM = 64 * 1024 * 1024

_COMMON = {
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password1",
    "qwertyui",
    "qwerty123",
    "abc12345",
    "11111111",
    "iloveyou",
    "senha123",
    "palavrapasse",
}


def _classes(password: str) -> int:
    return sum(
        (
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        )
    )


def password_level(password: str) -> int:
    if len(password) < 8 or password.lower() in _COMMON or len(set(password)) == 1:
        return 0
    return 1 + (len(password) >= 12) + (len(password) >= 16) + (_classes(password) >= 3)


def _scrypt(password: str, salt: bytes, n_log2: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=2**n_log2, r=r, p=p, maxmem=_SCRYPT_MAXMEM, dklen=32
    )


def hash_password(password: str) -> str:
    """`scrypt$<log2 N>$<r>$<p>$<sal>$<hash>` (base64); o sal é aleatório por password."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _scrypt(password, salt, _SCRYPT_N_LOG2, _SCRYPT_R, _SCRYPT_P)
    b64 = base64.b64encode
    params = f"{_SCRYPT_N_LOG2}${_SCRYPT_R}${_SCRYPT_P}"
    return f"scrypt${params}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n_log2, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = _scrypt(password, base64.b64decode(salt), int(n_log2), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)
