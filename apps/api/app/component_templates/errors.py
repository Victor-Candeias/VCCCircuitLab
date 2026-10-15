class TemplateNotFoundError(Exception):
    """Não existe nenhum template de componente com este id."""

    def __init__(self, template_id: str) -> None:
        self.template_id = template_id
        super().__init__(f"template {template_id} não encontrado")


class DuplicateTemplateTypeError(Exception):
    """Já existe um template com este `type` de componente."""

    def __init__(self, component_type: str) -> None:
        self.component_type = component_type
        super().__init__(f"já existe um template com type={component_type!r}")
