"""Erros de pedidos de geração: template desconhecido ou parâmetros inválidos.

Diferente de `app.circuit.errors.CircuitValidationError` (erros do próprio circuito): estes
erros acontecem antes de qualquer circuito existir, ao escolher o template e validar os seus
parâmetros (`app.generation.params`). São tratados centralmente em `app.problems`.
"""

from pydantic import ValidationError


class UnknownTemplateError(Exception):
    """`name` não está registado em `app.generation.registry.TEMPLATES`."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"template de geração desconhecido: {name}")


class InvalidParametersError(Exception):
    """Os parâmetros não passam na validação Pydantic do template `template`."""

    def __init__(self, template: str, cause: ValidationError) -> None:
        self.template = template
        self.cause = cause
        super().__init__(f"parâmetros inválidos para o template {template}")
