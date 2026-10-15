"""Catálogo: `GET /api/v1/components` (E2-06)."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.circuit.catalog import CATALOG_VERSION, DEFAULT_GRID_SIZE, load_catalog_documents
from app.models.component import ComponentDefinition

router = APIRouter(prefix="/api/v1", tags=["components"])


class ComponentCatalogResponse(BaseModel):
    catalog_version: str = Field(alias="catalogVersion")
    grid_size: float = Field(alias="gridSize")
    components: list[ComponentDefinition]

    model_config = {"populate_by_name": True}


def _load_catalog_response() -> ComponentCatalogResponse:
    # Lê os documentos em bruto da coleção `templates` (não o `ComponentSpec` reduzido usado
    # pelo solver) para expor também `description`, `category`, `idPrefix` e `symbol`,
    # necessários à paleta de componentes.
    documents = load_catalog_documents()
    components = [
        ComponentDefinition.model_validate(
            {**document, "supported": document.get("simulationModel") is not None}
        )
        for document in documents
    ]
    return ComponentCatalogResponse.model_validate(
        {
            "catalogVersion": CATALOG_VERSION,
            "gridSize": DEFAULT_GRID_SIZE,
            "components": components,
        }
    )


@router.get(
    "/components",
    response_model=ComponentCatalogResponse,
    response_model_by_alias=True,
    summary="Catálogo de componentes e schemas de propriedades",
)
def get_components() -> ComponentCatalogResponse:
    return _load_catalog_response()
