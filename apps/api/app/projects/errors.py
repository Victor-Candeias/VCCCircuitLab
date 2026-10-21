class ProjectNotFoundError(Exception):
    """O projeto não existe ou o utilizador não tem acesso (não se distingue, de propósito)."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"projeto {project_id} não encontrado")


class ProjectVersionConflictError(Exception):
    """O projeto foi gravado por outra pessoa depois de ter sido lido."""

    def __init__(self, current_version: int) -> None:
        self.current_version = current_version
        super().__init__(f"versão atual do projeto: {current_version}")


class ShareUserNotFoundError(Exception):
    """Não existe nenhuma conta com o email indicado na partilha."""


class InvalidShareError(Exception):
    """Partilha impossível (ex.: com o próprio dono ou acima do limite de convidados)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)
