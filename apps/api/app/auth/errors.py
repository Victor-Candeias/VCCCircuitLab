class InvalidCredentialsError(Exception):
    """Email ou password errados (sem indicar qual, para não revelar se o email existe)."""


class NotAuthorizedError(Exception):
    """Sessão válida, mas sem o role necessário para o recurso."""


class NotAuthenticatedError(Exception):
    """Pedido sem token de sessão, ou com um token inválido, expirado ou terminado."""
