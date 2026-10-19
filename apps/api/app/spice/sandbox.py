"""Lançador isolado do ngspice (F2-01).

Uso (só pelo `runner`, nunca com dados do utilizador nos argumentos):
    python -I sandbox.py <cpu_s> <memória_bytes> <ficheiro_bytes> -- <executável> [args…]

Baixa os limites de recursos do próprio processo (CPU, espaço de endereçamento, tamanho de
ficheiros, core dumps) e substitui-se pelo comando com `exec`, que herda esses limites. Evita o
`preexec_fn` do `subprocess`, inseguro com threads (a simulação corre numa thread do anyio).
Só usa a biblioteca padrão, para correr com `python -I`.
"""

import os
import resource
import sys


def _lower(limit: int, value: int) -> None:
    _soft, hard = resource.getrlimit(limit)
    if hard != resource.RLIM_INFINITY:
        value = min(value, hard)
    resource.setrlimit(limit, (value, value))


def main(argv: list[str]) -> None:
    if len(argv) < 5 or argv[3] != "--":
        raise SystemExit("uso: sandbox.py <cpu_s> <memória_bytes> <ficheiro_bytes> -- <comando…>")
    cpu_s, memory_bytes, file_bytes = (int(v) for v in argv[:3])
    command = argv[4:]
    _lower(resource.RLIMIT_CPU, cpu_s)
    if memory_bytes > 0:
        _lower(resource.RLIMIT_AS, memory_bytes)
    _lower(resource.RLIMIT_FSIZE, file_bytes)
    _lower(resource.RLIMIT_CORE, 0)
    os.execv(command[0], command)


if __name__ == "__main__":
    main(sys.argv[1:])
