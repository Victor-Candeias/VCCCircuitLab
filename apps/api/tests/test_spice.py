"""Motor ngspice (F2-01) sem depender do ngspice real: netlist, rawfile, execução isolada (com
um ngspice falso) e a API com `SIMULATION_ENGINE=ngspice`. A comparação com o ngspice real está
em `test_spice_ngspice.py`."""

import json
import os
import resource
import stat
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.circuit.catalog import load_catalog
from app.circuit.errors import CircuitErrorCode, CircuitValidationError
from app.circuit.validate import validate
from app.main import app
from app.models.circuit import CircuitDocument
from app.problems import SimulationTimeoutError
from app.routes import circuits
from app.solver.mna import simulate_dc
from app.spice.errors import SimulationEngineError
from app.spice.netlist import build_netlist
from app.spice.rawfile import parse_rawfile
from app.spice.runner import MAX_FILE_BYTES, NgspiceConfig, run_ngspice
from tests.factories import circuit, comp, load_fixture, source_resistor

SIMULATE = "/api/v1/circuits/simulate"
client = TestClient(app)

#: Rawfile do ngspice para `fonte-resistencia` (12 V, 100 Ω).
SOURCE_RESISTOR_RAW = """Title: * VCCCircuitLab
Date: Mon Jan  1 00:00:00  2024
Plotname: Operating Point
Flags: real
No. Variables: 2
No. Points: 1
Variables:
\t0\tv(n1)\tvoltage
\t1\ti(v1)\tcurrent
Values:
 0\t1.200000000000000e+01
\t-1.200000000000000e-01
"""

FakeNgspice = Callable[..., Path]


@pytest.fixture
def fake_ngspice(tmp_path: Path) -> FakeNgspice:
    """Cria um executável que se faz passar pelo ngspice (`ngspice -b circuit.cir`)."""

    def make(
        *, raw: str | None = SOURCE_RESISTOR_RAW, output: str = "", code: int = 0, sleep: float = 0
    ) -> Path:
        report = tmp_path / "report.json"
        script = tmp_path / "ngspice"
        script.write_text(
            f"""#!{sys.executable}
import json, os, resource, sys, time
from pathlib import Path
time.sleep({sleep!r})
limits = {{n: resource.getrlimit(getattr(resource, n))[0]
          for n in ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_FSIZE", "RLIMIT_CORE")}}
Path({str(report)!r}).write_text(json.dumps({{
    "argv": sys.argv[1:], "cwd": os.getcwd(), "env": sorted(os.environ),
    "netlist": Path(sys.argv[-1]).read_text(), "limits": limits,
    "pgid_is_own": os.getpgrp() == os.getpid(),
}}))
raw = {raw!r}
if raw is not None:
    Path("result.raw").write_text(raw)
print({output!r})
sys.exit({code!r})
""",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    return make


def report(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))


def netlist_of(data: dict[str, Any]) -> Any:
    catalog = load_catalog()
    normalized = validate(CircuitDocument.model_validate(data), catalog).raise_for_errors()
    return build_netlist(normalized, catalog)


class TestNetlist:
    def test_source_and_resistor(self) -> None:
        netlist = netlist_of(load_fixture("fonte-resistencia"))

        assert netlist.text.splitlines() == [
            "* VCCCircuitLab: ponto de funcionamento DC",
            "V1 n1 0 DC 12.0",
            "R2 n1 0 100.0",
            ".control",
            "set filetype=ascii",
            "op",
            "write result.raw",
            ".endc",
            ".end",
        ]
        assert netlist.nodes == {"N_PLUS": "n1", "N_GND": "0"}
        assert netlist.sources == {"V1": "v1"}

    def test_current_source_lamp_and_switches(self) -> None:
        data = circuit(
            [comp("I1", "dc_current_source"), comp("L1", "lamp")]
            + [comp("S1", "switch"), comp("S2", "switch", closed=False), comp("R1", "resistor")]
            + [comp("GND1", "ground")],
            ("I1.positive", "L1.a"),
            ("L1.b", "S1.a"),
            ("S1.b", "I1.negative"),
            ("I1.positive", "S2.a"),
            ("S2.b", "R1.a"),
            ("R1.b", "I1.negative"),
            ("GND1.gnd", "I1.negative"),
        )
        netlist = netlist_of(data)
        lines = netlist.text.splitlines()
        by_name = {line.split()[0]: line.split()[1:] for line in lines[1:] if line[0] in "RVI"}

        # A corrente sai por `positive`: no SPICE flui de n+ para n- dentro da fonte.
        assert by_name["I1"][0] == "0"
        assert by_name["I1"][2:] == ["DC", "0.1"]
        lamp_a = by_name["R2"][0]
        assert by_name["I1"][1] == lamp_a
        assert float(by_name["R2"][2]) == pytest.approx(28.8)
        assert by_name["V3"][2:] == ["DC", "0.0"]
        assert "V4" not in by_name
        assert by_name["R5"][2] == "100.0"
        assert netlist.sources == {"S1": "v3"}

    def test_user_text_never_reaches_the_netlist(self) -> None:
        data = source_resistor()
        data["name"] = ".include /etc/passwd"
        data["components"][1]["label"] = ".control\nshell rm -rf /"

        text = netlist_of(data).text

        assert "passwd" not in text
        assert "shell" not in text
        assert text.count(".control") == 1


class TestRawfile:
    def test_modern_names(self) -> None:
        raw = parse_rawfile(SOURCE_RESISTOR_RAW)

        assert raw.voltages == {"n1": 12.0}
        assert raw.currents == {"v1": -0.12}

    def test_legacy_names_and_values_on_one_line(self) -> None:
        text = (
            "Variables:\n 0 n1 voltage\n 1 N2 voltage\n 2 V1#branch current\n"
            "Values:\n0 5 2.5 -1e-3\n"
        )

        raw = parse_rawfile(text)

        assert raw.voltages == {"n1": 5.0, "n2": 2.5}
        assert raw.currents == {"v1": -0.001}

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "Variables:\n 0 v(n1) voltage\n",
            "Variables:\n 0 v(n1) voltage\n 1 i(v1) current\nValues:\n 0 1.0\n",
            "Variables:\n 0 v(n1) voltage\nValues:\n 0 nan?\n",
        ],
        ids=["empty", "no-values", "missing-value", "not-a-number"],
    )
    def test_malformed(self, text: str) -> None:
        with pytest.raises(SimulationEngineError):
            parse_rawfile(text)


class TestRunner:
    def test_runs_isolated_with_limits(self, fake_ngspice: FakeNgspice, tmp_path: Path) -> None:
        os.environ["VCCCL_TEST_SECRET"] = "nao-passar"
        try:
            raw = run_ngspice("* netlist\n", 2, NgspiceConfig(str(fake_ngspice()), 256))
        finally:
            del os.environ["VCCCL_TEST_SECRET"]

        assert raw.voltages == {"n1": 12.0}
        seen = report(tmp_path)
        assert seen["argv"] == ["-b", "circuit.cir"]
        assert seen["netlist"] == "* netlist\n"
        assert seen["env"] == ["HOME", "LANG", "LC_ALL", "PATH"]
        assert seen["pgid_is_own"] is True
        assert seen["limits"]["RLIMIT_CPU"] == 3
        assert seen["limits"]["RLIMIT_AS"] == 256 * 1024 * 1024
        assert seen["limits"]["RLIMIT_FSIZE"] == MAX_FILE_BYTES
        assert seen["limits"]["RLIMIT_CORE"] == 0
        assert not Path(seen["cwd"]).exists()

    def test_memory_limit_can_be_disabled(self, fake_ngspice: FakeNgspice, tmp_path: Path) -> None:
        run_ngspice("*\n", 2, NgspiceConfig(str(fake_ngspice()), 0))

        assert report(tmp_path)["limits"]["RLIMIT_AS"] == resource.getrlimit(resource.RLIMIT_AS)[0]

    def test_timeout_kills_the_process(self, fake_ngspice: FakeNgspice) -> None:
        started = time.perf_counter()
        with pytest.raises(SimulationTimeoutError):
            run_ngspice("*\n", 0.3, NgspiceConfig(str(fake_ngspice(sleep=10))))

        assert time.perf_counter() - started < 3

    def test_failure_is_an_engine_error(self, fake_ngspice: FakeNgspice) -> None:
        with pytest.raises(SimulationEngineError, match="código 1"):
            run_ngspice("*\n", 2, NgspiceConfig(str(fake_ngspice(raw=None, code=1))))

    def test_missing_rawfile_is_an_engine_error(self, fake_ngspice: FakeNgspice) -> None:
        with pytest.raises(SimulationEngineError):
            run_ngspice("*\n", 2, NgspiceConfig(str(fake_ngspice(raw=None))))

    def test_singular_matrix_is_a_circuit_error(self, fake_ngspice: FakeNgspice) -> None:
        script = fake_ngspice(raw=None, output="Error: singular matrix:  check node n1", code=1)

        with pytest.raises(CircuitValidationError) as excinfo:
            run_ngspice("*\n", 2, NgspiceConfig(str(script)))

        assert [e.code for e in excinfo.value.errors] == [CircuitErrorCode.SINGULAR_MATRIX]

    def test_singular_warning_with_result_is_success(self, fake_ngspice: FakeNgspice) -> None:
        script = fake_ngspice(output="Warning: singular matrix: gmin stepping succeeded")

        assert run_ngspice("*\n", 2, NgspiceConfig(str(script))).voltages == {"n1": 12.0}

    def test_config_from_env(
        self, fake_ngspice: FakeNgspice, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        script = fake_ngspice()
        monkeypatch.setenv("NGSPICE_PATH", str(script))
        monkeypatch.setenv("NGSPICE_MAX_MEMORY_MB", "128")

        assert NgspiceConfig.from_env() == NgspiceConfig(str(script), 128)

    @pytest.mark.parametrize(
        ("variable", "value"),
        [("NGSPICE_PATH", "/nao/existe/ngspice"), ("NGSPICE_MAX_MEMORY_MB", "muito")],
    )
    def test_bad_config(self, monkeypatch: pytest.MonkeyPatch, variable: str, value: str) -> None:
        monkeypatch.setenv("NGSPICE_PATH", sys.executable)
        monkeypatch.setenv(variable, value)

        with pytest.raises(SimulationEngineError):
            NgspiceConfig.from_env()


class TestApiWithNgspice:
    @pytest.fixture(autouse=True)
    def ngspice_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMULATION_ENGINE", "ngspice")

    def test_same_response_as_mna(
        self, fake_ngspice: FakeNgspice, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NGSPICE_PATH", str(fake_ngspice()))
        data = load_fixture("fonte-resistencia")

        response = client.post(SIMULATE, json=data)

        assert response.status_code == 200
        expected = simulate_dc(CircuitDocument.model_validate(data)).to_json_dict()
        assert response.json() == expected

    def test_invalid_circuit_is_rejected_before_ngspice(
        self, fake_ngspice: FakeNgspice, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("NGSPICE_PATH", str(fake_ngspice()))
        data = source_resistor()
        data["components"] = data["components"][:2]

        response = client.post(SIMULATE, json=data)

        assert response.status_code == 422
        assert not (tmp_path / "report.json").exists()

    def test_missing_ngspice_is_503_without_details(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NGSPICE_PATH", "/opt/segredo/ngspice")

        response = client.post(SIMULATE, json=source_resistor())

        assert response.status_code == 503
        body = response.json()
        assert body["code"] == "SIMULATION_ENGINE_ERROR"
        assert body["type"] == "urn:vcccircuitlab:problem:simulation-engine-error"
        assert "segredo" not in response.text

    def test_ngspice_timeout_is_503(
        self, fake_ngspice: FakeNgspice, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NGSPICE_PATH", str(fake_ngspice(sleep=10)))
        monkeypatch.setattr(circuits, "SIMULATION_TIMEOUT_S", 0.3)

        response = client.post(SIMULATE, json=source_resistor())

        assert response.status_code == 503
        assert response.json()["code"] == "SIMULATION_TIMEOUT"

    def test_unknown_engine_is_503(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIMULATION_ENGINE", "spectre")

        response = client.post(SIMULATE, json=source_resistor())

        assert response.status_code == 503
        assert response.json()["code"] == "SIMULATION_ENGINE_ERROR"
