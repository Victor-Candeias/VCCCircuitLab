"""Encriptação de campos em repouso (Fernet) e índice cego para pesquisas por igualdade.

A chave vem de `DATA_ENCRYPTION_KEY` (chave Fernet: 32 bytes em base64 URL-safe; gerar com
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
Perder a chave torna os dados encriptados irrecuperáveis.
"""

import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken
from dotenv import find_dotenv, load_dotenv

from app.db.errors import DatabaseUnavailableError

KEY_VARIABLE = "DATA_ENCRYPTION_KEY"
_INDEX_LABEL = b"vcccircuitlab/blind-index/v1"


class FieldCipher:
    def __init__(self, key: str) -> None:
        try:
            raw = base64.urlsafe_b64decode(key)
            self._fernet = Fernet(key)
        except ValueError as error:
            raise DatabaseUnavailableError(
                f"{KEY_VARIABLE} não é uma chave Fernet válida."
            ) from error
        if len(raw) != 32:
            raise DatabaseUnavailableError(f"{KEY_VARIABLE} não é uma chave Fernet válida.")
        # Chave própria do índice, derivada da principal: o HMAC nunca reutiliza a chave Fernet.
        self._index_key = hmac.new(raw, _INDEX_LABEL, hashlib.sha256).digest()

    def encrypt(self, text: str) -> str:
        return self._fernet.encrypt(text.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as error:
            raise ValueError("Valor encriptado inválido ou chave errada.") from error

    def blind_index(self, value: str) -> str:
        """HMAC-SHA256 determinístico: permite procurar/garantir unicidade sem guardar o valor."""
        return hmac.new(self._index_key, value.encode(), hashlib.sha256).hexdigest()


def get_cipher() -> FieldCipher:
    load_dotenv(find_dotenv(), override=False)
    key = os.environ.get(KEY_VARIABLE)
    if not key:
        raise DatabaseUnavailableError(f"Variável de ambiente {KEY_VARIABLE} em falta.")
    return FieldCipher(key)
