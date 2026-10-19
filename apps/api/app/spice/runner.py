"""Execução isolada do ngspice em modo batch (F2-01).

Cada simulação corre num diretório temporário próprio (apagado no fim), num grupo de processos
novo e com um ambiente mínimo. O processo passa pelo `sandbox` (limites de CPU, memória,
tamanho de ficheiros e core dumps) e é morto, com todo o grupo, se exceder o tempo máximo.

Configuração (variáveis de ambiente):

- `NGSPICE_PATH`: executável do ngspice (por omissão procura `ngspice` no `PATH`);
- `NGSPICE_MAX_MEMORY_MB`: limite do espaço de endereçamento (por omissão 512; 0 desliga).
"""

import contextlib
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.problems import SimulationTimeoutError
from app.spice import sandbox
from app.spice.errors import SimulationEngineError, singular_matrix_error
from app.spice.netlist import RAWFILE_NAME
from app.spice.rawfile import RawResult, parse_rawfile

logger = logging.getLogger(__name__)

NETLIST_NAME = "circuit.cir"
#: Tamanho máximo de cada ficheiro escrito pelo ngspice (rawfile, log).
MAX_FILE_BYTES = 16 * 1024 * 1024
#: Saída do ngspice guardada para diagnóstico (só no log do servidor).
MAX_OUTPUT_CHARS = 2000
_SINGULAR_MARKERS = ("singular matrix", "gmin stepping failed", "source stepping failed")


@dataclass(frozen=True)
class NgspiceConfig:
    executable: str
    max_memory_mb: int = 512

    @classmethod
    def from_env(cls) -> "NgspiceConfig":
        configured = os.environ.get("NGSPICE_PATH", "").strip()
        executable = shutil.which(configured or "ngspice")
        if executable is None:
            raise SimulationEngineError(f"ngspice não encontrado ({configured or 'PATH'})")
        try:
            memory = int(os.environ.get("NGSPICE_MAX_MEMORY_MB", "512"))
        except ValueError:
            raise SimulationEngineError("NGSPICE_MAX_MEMORY_MB não é um inteiro") from None
        return cls(executable=executable, max_memory_mb=max(memory, 0))


def run_ngspice(netlist: str, timeout_s: float, config: NgspiceConfig | None = None) -> RawResult:
    """Corre a netlist (com bloco `.control` que escreve `RAWFILE_NAME`) e lê o resultado."""
    config = config or NgspiceConfig.from_env()
    with tempfile.TemporaryDirectory(prefix="vcccl-spice-") as workdir:
        cwd = Path(workdir)
        (cwd / NETLIST_NAME).write_text(netlist, encoding="ascii")
        command = [
            sys.executable,
            "-I",
            sandbox.__file__,
            str(max(1, int(timeout_s) + 1)),
            str(config.max_memory_mb * 1024 * 1024),
            str(MAX_FILE_BYTES),
            "--",
            config.executable,
            "-b",
            NETLIST_NAME,
        ]
        env = {"PATH": "/usr/bin:/bin", "HOME": workdir, "LANG": "C", "LC_ALL": "C"}
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                start_new_session=True,
            )
        except OSError as exc:
            raise SimulationEngineError(f"não foi possível arrancar o ngspice: {exc}") from exc
        try:
            output, _ = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _kill_group(process)
            raise SimulationTimeoutError(timeout_s) from exc
        except BaseException:
            _kill_group(process)
            raise

        output = output or ""
        rawfile = cwd / RAWFILE_NAME
        if process.returncode == 0 and rawfile.is_file():
            # Avisos de matriz singular seguidos de convergência (gmin stepping) não são erro.
            return parse_rawfile(rawfile.read_text(encoding="ascii", errors="replace"))
        if any(marker in output.lower() for marker in _SINGULAR_MARKERS):
            raise singular_matrix_error()
        logger.warning(
            "ngspice falhou (código %s): %s", process.returncode, output[-MAX_OUTPUT_CHARS:]
        )
        raise SimulationEngineError(f"ngspice terminou com o código {process.returncode}")


def _kill_group(process: subprocess.Popen[str]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()
