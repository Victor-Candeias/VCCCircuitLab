"""Semeia a coleção `templates` a partir de um catálogo JSON (E5-06).

Uso, a partir de `apps/api`:

    python -m app.component_templates.seed ../../packages/circuit-schema/test/fixtures/catalog.json

O ficheiro tem o formato do catálogo (`{"components": [...]}`); cada componente é validado como
`TemplateCreate`. Só se inserem os tipos que ainda não existem (idempotente: não altera templates
já editados por administradores), com `createdBy: "seed"`. Serve para instalações novas (o
editor precisa de pelo menos um template) e para os testes E2E.
"""

import json
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pydantic import ValidationError
from pymongo.database import Database

from app.component_templates.service import COLLECTION, create_template
from app.db.collections import find
from app.db.errors import DatabaseUnavailableError
from app.db.mongo import close_client, get_database
from app.models.template import TemplateCreate

SEED_AUTHOR = "seed"


def load_components(path: Path) -> list[TemplateCreate]:
    data = json.loads(path.read_text(encoding="utf-8"))
    components = data.get("components") if isinstance(data, dict) else None
    if not isinstance(components, list):
        raise ValueError(f"{path}: falta a lista `components`")
    return [TemplateCreate.model_validate(c) for c in components]


def seed_templates(db: Database, components: list[TemplateCreate]) -> list[str]:
    """Insere os componentes cujo `type` ainda não existe; devolve os tipos inseridos."""
    existing = {d["type"] for d in find(db, COLLECTION, limit=1000)}
    inserted = []
    for component in components:
        if component.type not in existing:
            create_template(db, component, SEED_AUTHOR)
            existing.add(component.type)
            inserted.append(component.type)
    return inserted


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Uso: python -m app.component_templates.seed <catalog.json>", file=sys.stderr)
        return 2
    load_dotenv(find_dotenv(), override=False)
    try:
        components = load_components(Path(argv[0]))
    except (OSError, ValueError, ValidationError) as error:
        print(f"Catálogo inválido: {error}", file=sys.stderr)
        return 1
    try:
        inserted = seed_templates(get_database(), components)
    except DatabaseUnavailableError as error:
        print(f"Base de dados indisponível: {error}", file=sys.stderr)
        return 1
    finally:
        close_client()
    print(f"Templates inseridos: {len(inserted)} ({', '.join(inserted) or 'nenhum'}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
