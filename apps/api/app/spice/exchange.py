"""Importação/exportação de netlists SPICE (F2-05): tradutor netlist ↔ JSON canónico.

**Exportação** (`export_netlist`): o circuito validado (regras da análise transitória, as mais
permissivas) dá uma netlist legível, com os elementos nomeados a partir dos ids e `.op`. Os
componentes sem elemento SPICE (interruptor aberto, voltímetro, osciloscópio) só aparecem num
comentário. A rede CA (F2-07) é exportada como fonte sinusoidal (`SIN`, amplitude = valor eficaz
× √2); o disjuntor, o comutador (contacto ativo) e o diferencial (um elemento por polo)
fechados são fontes de 0 V. Depois de `.end` vai o documento canónico completo numa linha de
comentário (`*@vcccircuitlab {json}`, com as redes se existirem), que permite reimportar sem perdas.

**Importação** (`import_netlist`): se a netlist trouxer o documento embutido e os seus elementos
forem os que esse documento exporta (não foi editada), devolve-se o documento tal como estava.
Caso contrário, os elementos são traduzidos para componentes do catálogo:

- `R` → resistência; `C`/`L` → condensador/bobina (`IC=` → condição inicial);
- `V n+ n- [DC] v` → fonte de tensão (v < 0 troca os pinos; v = 0 → amperímetro);
- `I n+ n- [DC] i` → fonte de corrente: no SPICE a corrente sai por `n-`, que é o `positive`;
- `D a k modelo` → díodo (LED se o nome do modelo contiver "led"), com o ponto de condução
  (`forwardVoltageV` a `forwardCurrentA`) calculado de IS e N do `.model`. O solver usa
  N = 2, por isso a curva só coincide nesse ponto;
- `Q c b e [s] modelo` → transístor NPN/PNP (`BF` → `currentGain`, `IS` → `saturationCurrentA`);
- nó `0` (ou `gnd`) → componente de terra.

Os componentes ficam numa grelha e cada nó é uma cadeia de fios. Não há subcircuitos, fontes
não DC, fontes controladas, `.include`/`.lib`/`.param` nem outros elementos: são erros com o
número da linha. As diretivas de análise e de saída (`.op`, `.tran`, `.control` … `.endc`, …)
são ignoradas com um aviso. A netlist só é lida, nunca executada.
"""

import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from pydantic import ValidationError

from app.circuit.catalog import ComponentCatalog
from app.circuit.errors import CircuitError, CircuitValidationError
from app.circuit.validate import (
    AC_SOURCE_MODEL,
    AMMETER_MODEL,
    BJT_NPN_MODEL,
    BJT_PNP_MODEL,
    CAPACITOR_MODEL,
    CURRENT_SOURCE_MODEL,
    DIODE_MODEL,
    GROUND_MODEL,
    INDUCTOR_MODEL,
    MULTI_CONTACT_MODELS,
    SWITCH_MODELS,
    VOLTAGE_SOURCE_MODEL,
    contacts,
    validate,
)
from app.models.circuit import CircuitDocument, Component, Point, Wire
from app.solver.semiconductors import (
    BJT_REVERSE_GAIN,
    DIODE_EMISSION_COEFFICIENT,
    THERMAL_VOLTAGE_V,
)

EMBEDDED_PREFIX = "*@vcccircuitlab "
MAX_NETLIST_CHARS = 256 * 1024
MAX_ELEMENTS = 500
MAX_ERRORS = 20
GROUND_NODES = frozenset({"0", "gnd"})

#: Parâmetros SPICE por omissão (ngspice).
DEFAULT_DIODE_IS = 1e-14
DEFAULT_DIODE_N = 1.0
DEFAULT_BJT_IS = 1e-16
DEFAULT_BJT_BF = 100.0
DIODE_FORWARD_CURRENT_A = 0.01
LED_FORWARD_CURRENT_A = 0.02

#: Diretivas sem efeito no circuito (análises, saída, opções).
IGNORED_DIRECTIVES = frozenset(
    {
        ".op",
        ".tran",
        ".dc",
        ".ac",
        ".noise",
        ".tf",
        ".options",
        ".option",
        ".opt",
        ".print",
        ".plot",
        ".probe",
        ".save",
        ".temp",
        ".ic",
        ".nodeset",
        ".meas",
        ".measure",
        ".width",
        ".title",
    }
)

_SUFFIXES = {
    "t": Decimal("1e12"),
    "g": Decimal("1e9"),
    "meg": Decimal("1e6"),
    "k": Decimal("1e3"),
    "mil": Decimal("25.4e-6"),
    "m": Decimal("1e-3"),
    "u": Decimal("1e-6"),
    "µ": Decimal("1e-6"),
    "n": Decimal("1e-9"),
    "p": Decimal("1e-12"),
    "f": Decimal("1e-15"),
}
_NUMBER = re.compile(
    r"^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)(meg|mil|[tgkmuµnpf])?[a-zµΩ]*$", re.IGNORECASE
)
_INVALID_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]")


class NetlistIssueCode(StrEnum):
    INVALID_NETLIST = "INVALID_NETLIST"
    UNSUPPORTED_ELEMENT = "UNSUPPORTED_ELEMENT"
    UNSUPPORTED_DIRECTIVE = "UNSUPPORTED_DIRECTIVE"
    UNSUPPORTED_SOURCE = "UNSUPPORTED_SOURCE"
    UNKNOWN_MODEL = "UNKNOWN_MODEL"
    INVALID_VALUE = "INVALID_VALUE"
    # Avisos
    IGNORED_DIRECTIVE = "IGNORED_DIRECTIVE"
    IGNORED_PARAMETER = "IGNORED_PARAMETER"
    APPROXIMATE_MODEL = "APPROXIMATE_MODEL"
    EMBEDDED_CIRCUIT_IGNORED = "EMBEDDED_CIRCUIT_IGNORED"


@dataclass(frozen=True)
class NetlistIssue:
    code: NetlistIssueCode
    message: str
    line: int | None = None

    def text(self) -> str:
        return f"Linha {self.line}: {self.message}" if self.line else self.message


class InvalidNetlistError(Exception):
    """Netlist que não é possível traduzir (`issues` com o número da linha)."""

    def __init__(self, issues: list[NetlistIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(i.text() for i in issues))


@dataclass
class ImportResult:
    circuit: CircuitDocument
    warnings: list[NetlistIssue] = field(default_factory=list)
    circuit_issues: list[CircuitError] = field(default_factory=list)
    """Erros e avisos do validador sobre o circuito importado (para mostrar no editor)."""


# --- Exportação -----------------------------------------------------------------------------


def export_netlist(document: CircuitDocument, catalog: ComponentCatalog) -> str:
    """Netlist SPICE do circuito; lança `CircuitValidationError` se não for válido."""
    report = validate(document, catalog, analysis="export")
    normalized = report.raise_for_errors()
    net_of = normalized.terminal_to_net
    grounded = {
        net_of[c.terminal(pin)]
        for c in document.components
        if (spec := catalog.get(c.type)) is not None and spec.simulation_model == GROUND_MODEL
        for pin in spec.pins
    }
    nodes = _node_names([n.id for n in normalized.document.nets or []], grounded)
    names = _ElementNames()
    elements: list[str] = []
    models: list[str] = []
    omitted: list[str] = []
    for c in document.components:
        spec = catalog.get(c.type)
        assert spec is not None  # validado
        model = spec.simulation_model
        if model == GROUND_MODEL:
            continue
        node = {pin: nodes[net_of[c.terminal(pin)]] for pin in spec.pins}
        if model in MULTI_CONTACT_MODELS:
            line = "\n".join(
                f"{names.get('V', k.key.replace(':', '_'))} {node[k.a]} {node[k.b]} DC 0"
                for k in contacts(model, c)
                if k.closed
            )
        else:
            line = _element_line(c, model, list(node.values()), names, models)
        if not line:
            omitted.append(f"{c.id} ({spec.label})")
        else:
            elements.append(line)
    lines = [f"* {_single_line(document.name)}", "* Exportado pelo VCCCircuitLab (F2-05)."]
    if omitted:
        lines.append(f"* Sem elemento SPICE: {', '.join(omitted)}.")
    lines += [*elements, *models, ".op", ".end"]
    embedded = document.to_json_dict()
    lines.append(EMBEDDED_PREFIX + json.dumps(embedded, ensure_ascii=True, separators=(",", ":")))
    return "\n".join(lines) + "\n"


def _element_line(
    c: Component, model: str | None, n: list[str], names: "_ElementNames", models: list[str]
) -> str | None:
    p = c.properties
    if model == "resistor":
        return f"{names.get('R', c.id)} {n[0]} {n[1]} {_value(p['resistanceOhm'])}"
    if model == "resistive_lamp":
        resistance = float(p["ratedVoltageV"]) ** 2 / float(p["ratedPowerW"])
        return f"{names.get('R', c.id)} {n[0]} {n[1]} {_value(resistance)}"
    if model == CAPACITOR_MODEL:
        return (
            f"{names.get('C', c.id)} {n[0]} {n[1]} {_value(p['capacitanceF'])} "
            f"IC={_value(p['initialVoltageV'])}"
        )
    if model == INDUCTOR_MODEL:
        return (
            f"{names.get('L', c.id)} {n[0]} {n[1]} {_value(p['inductanceH'])} "
            f"IC={_value(p['initialCurrentA'])}"
        )
    if model == VOLTAGE_SOURCE_MODEL:
        return f"{names.get('V', c.id)} {n[0]} {n[1]} DC {_value(p['voltageV'])}"
    if model == AC_SOURCE_MODEL:
        amplitude = float(p["voltageV"]) * math.sqrt(2)
        return (
            f"{names.get('V', c.id)} {n[0]} {n[1]} "
            f"SIN(0 {_value(amplitude)} {_value(p['frequencyHz'])})"
        )
    if model == CURRENT_SOURCE_MODEL:
        return f"{names.get('I', c.id)} {n[1]} {n[0]} DC {_value(p['currentA'])}"
    if model == AMMETER_MODEL or (model in SWITCH_MODELS and p.get("closed") is True):
        return f"{names.get('V', c.id)} {n[0]} {n[1]} DC 0"
    if model == DIODE_MODEL:
        name = names.get("D", c.id)
        vt = DIODE_EMISSION_COEFFICIENT * THERMAL_VOLTAGE_V
        saturation = float(p["forwardCurrentA"]) / math.expm1(float(p["forwardVoltageV"]) / vt)
        # o nome do modelo dos LEDs contém "LED", para a importação os reconhecer
        model_name = f"{'LED' if c.type == 'led' else 'DM'}_{name}"
        models.append(
            f".model {model_name} D(IS={_value(saturation)} N={_value(DIODE_EMISSION_COEFFICIENT)})"
        )
        return f"{name} {n[0]} {n[1]} {model_name}"
    if model in (BJT_NPN_MODEL, BJT_PNP_MODEL):
        name = names.get("Q", c.id)
        kind = "NPN" if model == BJT_NPN_MODEL else "PNP"
        models.append(
            f".model QM_{name} {kind}(IS={_value(p['saturationCurrentA'])} "
            f"BF={_value(p['currentGain'])} BR={_value(BJT_REVERSE_GAIN)})"
        )
        return f"{name} {n[0]} {n[1]} {n[2]} QM_{name}"
    return None  # interruptor/disjuntor aberto, voltímetro, osciloscópio


class _ElementNames:
    """Nomes SPICE únicos (sem distinguir maiúsculas): letra do elemento + id do componente."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def get(self, letter: str, cid: str) -> str:
        base = cid.replace("-", "_")
        if not base.upper().startswith(letter):
            base = letter + base
        name, k = base, 2
        while name.lower() in self._used:
            name, k = f"{base}_{k}", k + 1
        self._used.add(name.lower())
        return name


def _node_names(nets: list[str], grounded: set[str]) -> dict[str, str]:
    """Nós com os ids das redes (`-` → `_`), únicos sem distinguir maiúsculas; terra → `0`."""
    nodes: dict[str, str] = {}
    used = set(GROUND_NODES)
    for net in nets:
        if net in grounded:
            nodes[net] = "0"
            continue
        base = net.replace("-", "_")
        name, k = base, 2
        while name.lower() in used:
            name, k = f"{base}_{k}", k + 1
        used.add(name.lower())
        nodes[net] = name
    return nodes


def _single_line(text: str) -> str:
    return "".join(" " if unicodedata.category(ch).startswith("C") else ch for ch in text)


def _value(value: object) -> str:
    return repr(float(value))  # type: ignore[arg-type]


# --- Importação -----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Line:
    number: int
    text: str

    @property
    def tokens(self) -> list[str]:
        return self.text.split()


@dataclass
class _Parsed:
    title: str
    elements: list[_Line]
    models: dict[str, tuple[str, dict[str, float], int]]
    """Nome (minúsculas) → (tipo, parâmetros em minúsculas, linha)."""
    embedded: str | None
    signature: list[str]
    warnings: list[NetlistIssue]
    errors: list[NetlistIssue]


def import_netlist(text: str, catalog: ComponentCatalog) -> ImportResult:
    """Documento canónico da netlist; lança `InvalidNetlistError` se não for traduzível."""
    if len(text) > MAX_NETLIST_CHARS:
        raise InvalidNetlistError(
            [_issue(NetlistIssueCode.INVALID_NETLIST, "a netlist é demasiado grande.")]
        )
    parsed = _parse(text)
    warnings = list(parsed.warnings)
    # O documento embutido vem primeiro: os elementos que não se traduzem (ex.: a rede CA, `SIN`)
    # não impedem reimportar uma netlist exportada e não editada.
    if parsed.embedded is not None and not parsed.errors:
        document = _embedded_document(parsed, catalog, warnings)
        if document is not None:
            return _result(document, [], catalog)
    builder = _Builder(catalog, parsed)
    builder.translate()
    errors = sorted([*parsed.errors, *builder.errors], key=lambda i: i.line or 0)
    if errors:
        raise InvalidNetlistError(errors[:MAX_ERRORS])
    document = builder.build()
    return _result(document, warnings + builder.warnings, catalog)


def _result(
    document: CircuitDocument, warnings: list[NetlistIssue], catalog: ComponentCatalog
) -> ImportResult:
    report = validate(document, catalog, analysis="export")
    return ImportResult(document, warnings, [*report.errors, *report.warnings])


def _issue(code: NetlistIssueCode, message: str, line: int | None = None) -> NetlistIssue:
    return NetlistIssue(code, message, line)


def _logical_lines(text: str) -> list[_Line]:
    """Linhas lógicas (continuações `+` juntas), sem comentários `;` / `$ ` no fim."""
    lines: list[_Line] = []
    for number, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        if number == 1:
            lines.append(_Line(1, raw.strip()))
            continue
        stripped = raw.strip()
        if stripped.startswith("*") or not stripped:
            lines.append(_Line(number, stripped))
            continue
        stripped = re.split(r";|\s\$\s|\s\$$", stripped, maxsplit=1)[0].strip()
        if stripped.startswith("+") and lines and lines[-1].text and lines[-1].number > 1:
            previous = lines[-1]
            if not previous.text.startswith("*"):
                lines[-1] = _Line(previous.number, f"{previous.text} {stripped[1:].strip()}")
                continue
        lines.append(_Line(number, stripped))
    return lines


def _normalize(text: str) -> str:
    text = re.sub(r"\s*=\s*", "=", text)
    return re.sub(r"[(),]", " ", text).strip()


def _parse(text: str) -> _Parsed:
    lines = _logical_lines(text)
    title = lines[0].text.lstrip("*").strip() if lines else ""
    elements: list[_Line] = []
    models: dict[str, tuple[str, dict[str, float], int]] = {}
    signature: list[str] = []
    warnings: list[NetlistIssue] = []
    errors: list[NetlistIssue] = []
    embedded: str | None = None
    ended = False
    in_control = False
    ignored: dict[str, int] = {}
    for line in lines[1:]:
        if line.text.startswith(EMBEDDED_PREFIX.rstrip()):
            embedded = line.text[len(EMBEDDED_PREFIX) :]
            continue
        if ended or not line.text or line.text.startswith("*"):
            continue
        lower = line.text.lower()
        keyword = lower.split()[0]
        if in_control:
            in_control = keyword != ".endc"
            continue
        if keyword == ".control":
            in_control = True
            ignored.setdefault(keyword, line.number)
            continue
        if keyword == ".end":
            ended = True
            continue
        normalized = _normalize(line.text)
        if keyword.startswith("."):
            if keyword == ".model":
                signature.append(" ".join(normalized.lower().split()))
                _parse_model(_Line(line.number, normalized), models, errors)
            elif keyword in IGNORED_DIRECTIVES:
                ignored.setdefault(keyword, line.number)
            else:
                errors.append(
                    _issue(
                        NetlistIssueCode.UNSUPPORTED_DIRECTIVE,
                        f"a diretiva {keyword} não é suportada.",
                        line.number,
                    )
                )
            continue
        signature.append(" ".join(normalized.lower().split()))
        elements.append(_Line(line.number, normalized))
    if len(elements) > MAX_ELEMENTS:
        errors.append(
            _issue(
                NetlistIssueCode.INVALID_NETLIST,
                f"a netlist tem mais de {MAX_ELEMENTS} elementos.",
            )
        )
    for keyword, number in ignored.items():
        if keyword == ".op":
            continue  # a análise escolhe-se no editor; `.op` é o que a exportação escreve
        warnings.append(
            _issue(
                NetlistIssueCode.IGNORED_DIRECTIVE,
                f"a diretiva {keyword} foi ignorada (a análise escolhe-se no editor).",
                number,
            )
        )
    return _Parsed(title, elements, models, embedded, signature, warnings, errors)


def _parse_model(
    line: _Line,
    models: dict[str, tuple[str, dict[str, float], int]],
    errors: list[NetlistIssue],
) -> None:
    tokens = line.tokens
    if len(tokens) < 3:
        errors.append(_issue(NetlistIssueCode.INVALID_NETLIST, "`.model` incompleto.", line.number))
        return
    params: dict[str, float] = {}
    for token in tokens[3:]:
        key, sep, raw = token.partition("=")
        value = parse_value(raw) if sep else None
        if value is None:
            errors.append(
                _issue(
                    NetlistIssueCode.INVALID_VALUE,
                    f"parâmetro inválido {token!r} no modelo {tokens[1]}.",
                    line.number,
                )
            )
            continue
        params[key.lower()] = value
    models[tokens[1].lower()] = (tokens[2].lower(), params, line.number)


def parse_value(token: str) -> float | None:
    """Valor SPICE (`10k`, `4.7u`, `1meg`, `2.2nF`, …) ou `None` se não for um número."""
    match = _NUMBER.match(token.strip())
    if match is None:
        return None
    # em decimal, para `100n` dar 1e-07 e não 1.0000000000000001e-07
    scale = _SUFFIXES.get((match.group(2) or "").lower(), Decimal(1))
    number = float(Decimal(match.group(1)) * scale)
    return number if math.isfinite(number) else None


def _embedded_document(
    parsed: _Parsed, catalog: ComponentCatalog, warnings: list[NetlistIssue]
) -> CircuitDocument | None:
    """Documento embutido, se a netlist não foi editada depois da exportação."""
    try:
        document = CircuitDocument.model_validate(json.loads(parsed.embedded or ""))
        exported = _parse(export_netlist(document, catalog))
    except (ValueError, ValidationError, CircuitValidationError):
        exported = None
    if exported is not None and exported.signature == parsed.signature:
        return document
    warnings.append(
        _issue(
            NetlistIssueCode.EMBEDDED_CIRCUIT_IGNORED,
            "o circuito do VCCCircuitLab guardado na netlist não corresponde aos elementos "
            "(a netlist foi editada); o desenho foi gerado a partir dos elementos.",
        )
    )
    return None


@dataclass
class _Pending:
    id: str
    type: str
    properties: dict[str, float | bool]
    nodes: list[str]


class _Builder:
    """Traduz os elementos para componentes e gera o desenho (grelha + fios por nó)."""

    COLUMNS = 4

    def __init__(self, catalog: ComponentCatalog, parsed: _Parsed) -> None:
        self.catalog = catalog
        self.parsed = parsed
        self.components: list[_Pending] = []
        self.ids: set[str] = set()
        self.warnings: list[NetlistIssue] = []
        self.errors: list[NetlistIssue] = []
        self._warned_models: set[str] = set()

    def translate(self) -> None:
        """Traduz os elementos, juntando os erros em `errors`."""
        for line in self.parsed.elements:
            self._element(line)

    def build(self) -> CircuitDocument:
        if not self.components:
            raise InvalidNetlistError(
                [_issue(NetlistIssueCode.INVALID_NETLIST, "a netlist não tem elementos.")]
            )
        for component_type in {p.type for p in self.components} | {"ground"}:
            if self.catalog.get(component_type) is None:
                raise InvalidNetlistError(
                    [
                        _issue(
                            NetlistIssueCode.UNSUPPORTED_ELEMENT,
                            f"o tipo {component_type} não existe no catálogo de componentes.",
                        )
                    ]
                )
        return self._layout()

    # -- elementos ---------------------------------------------------------------------------

    def _error(self, code: NetlistIssueCode, message: str, line: _Line) -> None:
        self.errors.append(_issue(code, message, line.number))

    def _add(self, line: _Line, ctype: str, properties: dict, nodes: list[str]) -> None:
        base = _INVALID_ID_CHARS.sub("_", line.tokens[0])[:64]
        if not base[0].isalpha():
            base = f"X{base}"[:64]
        cid, k = base, 2
        while cid in self.ids:
            suffix = f"_{k}"
            cid, k = base[: 64 - len(suffix)] + suffix, k + 1
        self.ids.add(cid)
        self.components.append(_Pending(cid, ctype, properties, [n.lower() for n in nodes]))

    def _element(self, line: _Line) -> None:
        tokens = line.tokens
        letter = tokens[0][0].upper()
        handler = {
            "R": self._passive,
            "C": self._passive,
            "L": self._passive,
            "V": self._source,
            "I": self._source,
            "D": self._diode,
            "Q": self._bjt,
        }.get(letter)
        if handler is None:
            self._error(
                NetlistIssueCode.UNSUPPORTED_ELEMENT,
                f"o elemento {tokens[0]} não é suportado (só R, C, L, V, I, D e Q).",
                line,
            )
            return
        handler(line)

    def _value_at(self, line: _Line, index: int, what: str) -> float | None:
        tokens = line.tokens
        if len(tokens) <= index:
            self._error(NetlistIssueCode.INVALID_NETLIST, f"falta {what} em {tokens[0]}.", line)
            return None
        value = parse_value(tokens[index])
        if value is None:
            self._error(
                NetlistIssueCode.INVALID_VALUE,
                f"{what} inválido em {tokens[0]}: {tokens[index]!r}.",
                line,
            )
        return value

    def _ignore_extra(self, line: _Line, extra: list[str]) -> None:
        if extra:
            self.warnings.append(
                _issue(
                    NetlistIssueCode.IGNORED_PARAMETER,
                    f"parâmetros ignorados em {line.tokens[0]}: {' '.join(extra)}.",
                    line.number,
                )
            )

    def _passive(self, line: _Line) -> None:
        tokens = line.tokens
        letter = tokens[0][0].upper()
        value = self._value_at(line, 3, "o valor")
        if value is None:
            return
        initial = 0.0
        extra: list[str] = []
        for token in tokens[4:]:
            key, sep, raw = token.partition("=")
            if letter in "CL" and sep and key.lower() == "ic" and parse_value(raw) is not None:
                initial = parse_value(raw) or 0.0
            else:
                extra.append(token)
        self._ignore_extra(line, extra)
        nodes = tokens[1:3]
        if letter == "R":
            self._add(line, "resistor", {"resistanceOhm": value}, nodes)
        elif letter == "C":
            props = {"capacitanceF": value, "initialVoltageV": initial}
            self._add(line, "capacitor", props, nodes)
        else:
            self._add(line, "inductor", {"inductanceH": value, "initialCurrentA": initial}, nodes)

    def _source(self, line: _Line) -> None:
        tokens = line.tokens
        letter = tokens[0][0].upper()
        if len(tokens) < 4:
            self._error(NetlistIssueCode.INVALID_NETLIST, f"falta o valor em {tokens[0]}.", line)
            return
        rest = tokens[3:]
        functions = {"pulse", "sin", "pwl", "exp", "sffm", "am", "trnoise", "trrandom"}
        if any(t.lower() in functions for t in rest):
            self._error(
                NetlistIssueCode.UNSUPPORTED_SOURCE,
                f"a fonte {tokens[0]} não é DC (só fontes DC são suportadas).",
                line,
            )
            return
        if rest[0].lower() == "dc":
            rest = rest[1:]
        if not rest or (value := parse_value(rest[0])) is None:
            self._error(NetlistIssueCode.INVALID_VALUE, f"valor DC inválido em {tokens[0]}.", line)
            return
        self._ignore_extra(line, rest[1:])
        plus, minus = tokens[1], tokens[2]
        if letter == "V":
            if value == 0:
                self._add(line, "ammeter", {}, [plus, minus])
            elif value > 0:
                self._add(line, "dc_voltage_source", {"voltageV": value}, [plus, minus])
            else:
                self._add(line, "dc_voltage_source", {"voltageV": -value}, [minus, plus])
            return
        if value == 0:
            self.warnings.append(
                _issue(
                    NetlistIssueCode.IGNORED_PARAMETER,
                    f"a fonte de corrente nula {tokens[0]} foi omitida (é um circuito aberto).",
                    line.number,
                )
            )
        elif value > 0:
            self._add(line, "dc_current_source", {"currentA": value}, [minus, plus])
        else:
            self._add(line, "dc_current_source", {"currentA": -value}, [plus, minus])

    def _model(self, line: _Line, name: str, kinds: set[str]) -> tuple[str, dict[str, float]]:
        model = self.parsed.models.get(name.lower())
        if model is None or model[0] not in kinds:
            expected = "/".join(sorted(k.upper() for k in kinds))
            self._error(
                NetlistIssueCode.UNKNOWN_MODEL,
                f"o modelo {name} de {line.tokens[0]} não existe "
                f"(é preciso um `.model` {expected}).",
                line,
            )
            return "", {}
        return model[0], model[1]

    def _warn_model(self, line: _Line, name: str, params: dict[str, float], known: set[str]):
        extra = sorted(set(params) - known)
        if extra and name.lower() not in self._warned_models:
            self._warned_models.add(name.lower())
            self.warnings.append(
                _issue(
                    NetlistIssueCode.IGNORED_PARAMETER,
                    f"parâmetros do modelo {name} ignorados: {', '.join(extra).upper()}.",
                    line.number,
                )
            )

    def _diode(self, line: _Line) -> None:
        tokens = line.tokens
        if len(tokens) < 4:
            self._error(NetlistIssueCode.INVALID_NETLIST, f"falta o modelo em {tokens[0]}.", line)
            return
        kind, params = self._model(line, tokens[3], {"d"})
        if not kind:
            return
        self._ignore_extra(line, tokens[4:])
        self._warn_model(line, tokens[3], params, {"is", "n"})
        saturation = params.get("is", DEFAULT_DIODE_IS)
        emission = params.get("n", DEFAULT_DIODE_N)
        is_led = "led" in tokens[3].lower()
        current = LED_FORWARD_CURRENT_A if is_led else DIODE_FORWARD_CURRENT_A
        if saturation <= 0 or emission <= 0:
            self._error(
                NetlistIssueCode.INVALID_VALUE,
                f"IS e N do modelo {tokens[3]} têm de ser positivos.",
                line,
            )
            return
        voltage = emission * THERMAL_VOLTAGE_V * math.log1p(current / saturation)
        if emission != DIODE_EMISSION_COEFFICIENT:
            self.warnings.append(
                _issue(
                    NetlistIssueCode.APPROXIMATE_MODEL,
                    f"{tokens[0]}: o simulador usa N = 2; o díodo passa no ponto "
                    f"{voltage:.3g} V a {current * 1000:g} mA do modelo {tokens[3]}, mas a "
                    "curva fora desse ponto é aproximada.",
                    line.number,
                )
            )
        props = {"forwardVoltageV": round(voltage, 6), "forwardCurrentA": current}
        self._add(line, "led" if is_led else "diode", props, tokens[1:3])

    def _bjt(self, line: _Line) -> None:
        tokens = line.tokens
        models = self.parsed.models
        if len(tokens) >= 6 and tokens[5].lower() in models and tokens[4].lower() not in models:
            model_index = 5  # com substrato
        else:
            model_index = 4
        if len(tokens) <= model_index:
            self._error(NetlistIssueCode.INVALID_NETLIST, f"falta o modelo em {tokens[0]}.", line)
            return
        kind, params = self._model(line, tokens[model_index], {"npn", "pnp"})
        if not kind:
            return
        self._ignore_extra(line, tokens[model_index + 1 :])  # o substrato não conta
        self._warn_model(line, tokens[model_index], params, {"is", "bf", "br"})
        if params.get("br", BJT_REVERSE_GAIN) != BJT_REVERSE_GAIN:
            self.warnings.append(
                _issue(
                    NetlistIssueCode.APPROXIMATE_MODEL,
                    f"{tokens[0]}: o simulador usa BR = 1 (ganho inverso).",
                    line.number,
                )
            )
        props = {
            "currentGain": params.get("bf", DEFAULT_BJT_BF),
            "saturationCurrentA": params.get("is", DEFAULT_BJT_IS),
        }
        ctype = "npn_transistor" if kind == "npn" else "pnp_transistor"
        self._add(line, ctype, props, tokens[1:4])

    # -- desenho -----------------------------------------------------------------------------

    def _layout(self) -> CircuitDocument:
        grid = self.catalog.grid_size
        origin_x, origin_y = 6 * grid, 6 * grid
        cell_w, cell_h = 10 * grid, 8 * grid
        components: list[Component] = []
        terminals: dict[str, list[tuple[float, float, str]]] = {}
        for k, pending in enumerate(self.components):
            row, column = divmod(k, self.COLUMNS)
            x, y = origin_x + column * cell_w, origin_y + row * cell_h
            spec = self.catalog.get(pending.type)
            assert spec is not None
            components.append(
                Component(
                    id=pending.id,
                    type=pending.type,
                    position=Point(x=x, y=y),
                    rotation=0,
                    properties=pending.properties,
                    pins=list(spec.pins),
                )
            )
            for pin, node in zip(spec.pins, pending.nodes, strict=True):
                dx, dy = spec.pin_positions[pin]
                key = "0" if node in GROUND_NODES else node
                terminals.setdefault(key, []).append((x + dx, y + dy, f"{pending.id}.{pin}"))
        if "0" in terminals:
            ground_id, k = "GND1", 2
            while ground_id in self.ids:
                ground_id, k = f"GND{k}", k + 1
            spec = self.catalog.get("ground")
            assert spec is not None
            rows = math.ceil(len(self.components) / self.COLUMNS)
            x, y = origin_x - 2 * grid, origin_y + rows * cell_h
            components.append(
                Component(
                    id=ground_id,
                    type="ground",
                    position=Point(x=x, y=y),
                    rotation=0,
                    properties={},
                    pins=list(spec.pins),
                )
            )
            dx, dy = spec.pin_positions[spec.pins[0]]
            terminals["0"].append((x + dx, y + dy, f"{ground_id}.{spec.pins[0]}"))
        wires: list[Wire] = []
        for points in terminals.values():
            chain = sorted(points)
            for (_, _, a), (_, _, b) in zip(chain, chain[1:], strict=False):
                wires.append(Wire(id=f"W{len(wires) + 1}", from_=a, to=b, waypoints=[]))
        name = _single_line(self.parsed.title)[:200].strip() or "Netlist SPICE importada"
        document = CircuitDocument(
            schema_version="1.0",
            id="netlist-spice",
            name=name,
            units="SI",
            components=components,
            wires=wires,
        )
        return document
