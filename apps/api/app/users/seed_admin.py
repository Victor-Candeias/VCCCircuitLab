"""Cria (ou repõe) o utilizador administrador na BD.

Uso, a partir de `apps/api`:  python -m app.users.seed_admin

Lê `ADMIN_EMAIL` e `ADMIN_PASSWORD` (obrigatórias) e `ADMIN_NAME` (por omissão
`Administrador`) do ambiente ou do `.env`. É idempotente: se o email já existir, repõe o role
`ADMIN` e a password.
"""

import os
import sys

from dotenv import find_dotenv, load_dotenv

from app.db.errors import DatabaseUnavailableError
from app.db.mongo import close_client, get_database
from app.security.crypto import get_cipher
from app.users.service import ensure_admin


def main() -> int:
    load_dotenv(find_dotenv(), override=False)
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    name = os.environ.get("ADMIN_NAME", "").strip() or "Administrador"
    if not email or not password:
        print("Defina ADMIN_EMAIL e ADMIN_PASSWORD no ambiente ou no .env.", file=sys.stderr)
        return 1
    try:
        admin_id = ensure_admin(get_database(), get_cipher(), name, email, password)
    except DatabaseUnavailableError as error:
        print(f"Base de dados indisponível: {error}", file=sys.stderr)
        return 1
    finally:
        close_client()
    print(f"Administrador pronto (id {admin_id}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
