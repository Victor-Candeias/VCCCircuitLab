from app.circuit.errors import CircuitError, CircuitErrorCode, CircuitValidationError


class SimulationEngineError(Exception):
    """O motor de simulação externo (ngspice) não está disponível ou falhou.

    A mensagem é só para o log do servidor; o cliente recebe uma resposta genérica (503).
    """


def singular_matrix_error() -> CircuitValidationError:
    """Mesmo erro que o solver MNA dá a um sistema sem solução única (422)."""
    return CircuitValidationError(
        [
            CircuitError(
                CircuitErrorCode.SINGULAR_MATRIX,
                "O sistema de equações é singular: o circuito não tem solução única.",
            )
        ]
    )
