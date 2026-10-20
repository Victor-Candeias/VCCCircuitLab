"""Interpretação de pedidos em linguagem natural (português) para os templates de geração.

Parser de intenções determinístico, sem LLM nem serviços externos: o texto só escolhe um dos
templates registados em `app.generation.registry` e os seus parâmetros. O resultado passa
sempre pelo modelo Pydantic do template (schema) e, depois de gerado, pelo validador elétrico;
o texto nunca é executado nem transformado em código.

Exemplos aceites:

- «circuito em série com fonte de 12 V e resistências de 100, 220 e 330 Ω»
- «divisor de tensão de 9V com 10k e 4,7k»
- «três resistências de 1 kΩ em paralelo com uma bateria de 5 V»
- «interruptor aberto com uma lâmpada de 50 ohm a 24 V»
- «iluminação de escada com lâmpada de 100 W e disjuntor de 16 A» (F2-08, rede de 230 V)

O que não é dito explicitamente (tensão, resistências, estado do interruptor, topologia) recebe
um valor por omissão e fica registado em `Interpretation.assumptions`, para o utilizador o
confirmar antes de abrir o circuito no editor.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from pydantic import ValidationError

from app.generation.errors import InvalidParametersError, UninterpretableTextError
from app.generation.registry import get_template

#: Tamanho máximo do texto aceite (caracteres).
MAX_TEXT_CHARS = 1000
#: Número máximo de resistências (igual ao limite dos templates).
MAX_RESISTORS = 12

_DEFAULT_VOLTAGE_V = 12.0
_DEFAULT_RESISTORS_OHM: dict[str, list[float]] = {
    "series_dc": [100.0, 220.0],
    "parallel_dc": [100.0, 200.0],
    "voltage_divider": [100.0, 100.0],
    "switch_circuit": [100.0],
}

_PREFIXES = {
    "meg": Decimal("1e6"),
    "M": Decimal("1e6"),
    "G": Decimal("1e9"),
    "k": Decimal("1e3"),
    "K": Decimal("1e3"),
    "m": Decimal("1e-3"),
    "u": Decimal("1e-6"),
    "µ": Decimal("1e-6"),
}

_QUANTITY = re.compile(
    r"(?<![\w.])(?P<number>\d+(?:\.\d+)?)\s*"
    r"(?P<prefix>meg|Meg|MEG|[kKMGmuµ])?\s*"
    r"(?P<unit>volts?|Volts?|VOLTS?|V|v|ohms?|Ohms?|OHMS?|Ω|amperes?|A|watts?|W|"
    r"farads?|F|henrys?|H|hertz|Hz)?"
    r"(?![\w])"
)
_DECIMAL_COMMA = re.compile(r"(?<=\d),(?=\d)")
_LIST_SEPARATOR = re.compile(r"^(?:\s|,|;|/|\be\b)+$")

_NUMBER_WORDS = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
    "dez": 10,
    "onze": 11,
    "doze": 12,
}
_LOAD_NOUN = r"(?:resistencias?|resistores?|resistors?|lampadas?|cargas?)"
_COUNT = re.compile(rf"\b(?P<count>\d+|{'|'.join(_NUMBER_WORDS)})\s+{_LOAD_NOUN}\b", re.IGNORECASE)
_VOLTAGE_CONTEXT = re.compile(
    r"\b(?:fonte|bateria|pilha|tensao|alimentacao|alimentado|alimentada)\b"
    r"(?:\s+(?:de|com|a|em|dc|cc|continua))*\s*$"
)
_LOAD_CONTEXT = re.compile(rf"\b{_LOAD_NOUN}\b(?:\s+(?:de|com|a|em))*\s*$")

_KEYWORDS: dict[str, re.Pattern[str]] = {
    "voltage_divider": re.compile(r"\bdivisor(?:es)?\b"),
    "switch_circuit": re.compile(r"\b(?:interruptor|interruptores|comutador|switch)\b"),
    "parallel_dc": re.compile(r"\bparalelos?\b"),
    "series_dc": re.compile(r"\bseries?\b"),
}
_OPEN = re.compile(r"\b(?:aberto|aberta|desligado|desligada|off)\b")
_CLOSED = re.compile(r"\b(?:fechado|fechada|on)\b")
_LAMP = re.compile(r"\blampadas?\b")
_AC = re.compile(r"\b(?:ac|alternada|sinusoidal|sinusoide)\b")
_STAIRCASE = re.compile(r"\b(?:escadas?|lustre)\b")
_LIT = re.compile(r"\b(?:acesa|acesas|ligada|ligadas)\b")
_UNLIT = re.compile(r"\b(?:apagada|apagadas|desligada|desligadas)\b")

#: Parâmetros de `staircase_lighting` por unidade, com o valor por omissão e a descrição.
_STAIRCASE_UNITS: dict[str, tuple[str, float, str]] = {
    "V": ("voltageV", 230.0, "tensão da rede"),
    "Hz": ("frequencyHz", 50.0, "frequência da rede"),
    "W": ("lampPowerW", 60.0, "potência da lâmpada"),
    "A": ("breakerRatedA", 10.0, "corrente estipulada do disjuntor"),
}

_UNSUPPORTED_UNITS = {
    "A": "corrente (A)",
    "W": "potência (W)",
    "F": "capacidade (F)",
    "H": "indutância (H)",
    "Hz": "frequência (Hz)",
}

Kind = Literal["voltage", "resistance"]


@dataclass(frozen=True)
class Interpretation:
    template: str
    #: Parâmetros já validados pelo modelo do template (nomes JSON em camelCase).
    parameters: dict[str, Any]
    #: Resumo legível do circuito interpretado.
    summary: str
    #: Valores assumidos por omissão ou interpretações a confirmar.
    assumptions: list[str] = field(default_factory=list)
    params: Any = None


@dataclass
class _Quantity:
    start: int
    end: int
    raw: str
    value: float
    unit: str | None
    kind: Kind | None = None


def _fold(text: str) -> str:
    """Minúsculas e sem acentos, com o mesmo comprimento do texto (para alinhar posições)."""
    folded = []
    for char in text:
        base = unicodedata.normalize("NFKD", char)[0]
        folded.append(base.lower() if len(base.lower()) == 1 else char)
    return "".join(folded)


def _unit(token: str | None) -> str | None:
    if token is None:
        return None
    lowered = token.lower()
    if lowered.startswith("volt") or lowered == "v":
        return "V"
    if lowered.startswith("ohm") or token == "Ω":
        return "Ω"
    if lowered.startswith("ampere"):
        return "A"
    if lowered.startswith("watt"):
        return "W"
    if lowered.startswith("farad"):
        return "F"
    if lowered.startswith("henry"):
        return "H"
    if lowered == "hertz":
        return "Hz"
    return token


def _quantities(
    text: str, reasons: list[str], allowed: frozenset[str] = frozenset()
) -> list[_Quantity]:
    found: list[_Quantity] = []
    for match in _QUANTITY.finditer(text):
        prefix = match.group("prefix")
        unit = _unit(match.group("unit"))
        if unit in _UNSUPPORTED_UNITS and unit not in allowed:
            reasons.append(
                f"«{match.group(0).strip()}»: só se indicam tensão (V) e resistências (Ω); "
                f"{_UNSUPPORTED_UNITS[unit]} não é suportada."
            )
            continue
        scale = _PREFIXES.get(prefix, Decimal(1)) if prefix else Decimal(1)
        value = float(Decimal(match.group("number")) * scale)
        kind: Kind | None = None
        if unit == "V":
            kind = "voltage"
        elif unit == "Ω" or prefix is not None:
            kind = "resistance"
        found.append(
            _Quantity(match.start(), match.end(), match.group(0).strip(), value, unit, kind)
        )
    return found


def _drop_counts(folded: str, quantities: list[_Quantity]) -> tuple[int | None, list[_Quantity]]:
    """Separa as contagens («3 resistências») dos valores; devolve a primeira contagem."""
    count: int | None = None
    count_starts: set[int] = set()
    for match in _COUNT.finditer(folded):
        word = match.group("count").lower()
        number = int(word) if word.isdigit() else _NUMBER_WORDS[word]
        count_starts.add(match.start("count"))
        if count is None:
            count = number
    values = [q for q in quantities if not (q.start in count_starts and q.kind is None)]
    return count, values


def _classify(folded: str, quantities: list[_Quantity]) -> None:
    """Classifica os números sem unidade pelo contexto ou pela lista a que pertencem."""
    for quantity in quantities:
        if quantity.kind is not None:
            continue
        before = folded[max(0, quantity.start - 40) : quantity.start]
        if _VOLTAGE_CONTEXT.search(before):
            quantity.kind = "voltage"
        elif _LOAD_CONTEXT.search(before):
            quantity.kind = "resistance"
    # Listas («100, 220 e 330 Ω»): um número sem unidade toma a unidade da resistência vizinha.
    changed = True
    while changed:
        changed = False
        for left, right in zip(quantities, quantities[1:], strict=False):
            if not _LIST_SEPARATOR.match(folded[left.end : right.start]):
                continue
            if left.kind is None and right.kind == "resistance":
                left.kind = "resistance"
                changed = True
            elif right.kind is None and left.kind == "resistance":
                right.kind = "resistance"
                changed = True


def _choose_template(folded: str, reasons: list[str]) -> tuple[str | None, bool]:
    """Template pedido e se foi inferido (sem palavra-chave de topologia)."""
    matched = [name for name, pattern in _KEYWORDS.items() if pattern.search(folded)]
    for name in ("voltage_divider", "switch_circuit"):
        if name in matched:
            return name, False
    if "parallel_dc" in matched and "series_dc" in matched:
        reasons.append(
            "O texto pede série e paralelo ao mesmo tempo; os circuitos mistos ainda não são "
            "gerados — escolha uma das topologias."
        )
        return None, False
    if matched:
        return matched[0], False
    return None, True


def _format_value(value: float, unit: str) -> str:
    for scale, prefix in ((1e6, "M"), (1e3, "k")):
        if value >= scale:
            return f"{value / scale:g} {prefix}{unit}"
    return f"{value:g} {unit}"


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} e {items[-1]}"


def interpret(text: str) -> Interpretation:
    """Interpreta `text` como um pedido de circuito.

    Lança `UninterpretableTextError` se o texto não descrever um circuito suportado e
    `InvalidParametersError` se os valores encontrados não passarem no schema do template.
    """
    text = unicodedata.normalize("NFC", text).replace("\u2126", "Ω")
    text = _DECIMAL_COMMA.sub(".", text)
    folded = _fold(text)
    if _STAIRCASE.search(folded):
        return _interpret_staircase(text, folded)
    reasons: list[str] = []
    assumptions: list[str] = []

    quantities = _quantities(text, reasons)
    count, quantities = _drop_counts(folded, quantities)
    _classify(folded, quantities)
    for quantity in quantities:
        if quantity.kind is None:
            reasons.append(
                f"Não é claro a que se refere o valor «{quantity.raw}»; indique a unidade "
                "(V para a fonte, Ω para resistências)."
            )
    voltages = [q.value for q in quantities if q.kind == "voltage"]
    resistors = [q.value for q in quantities if q.kind == "resistance"]
    if len(voltages) > 1:
        reasons.append("Só é suportada uma fonte de tensão; o texto indica mais de uma tensão.")

    template, inferred = _choose_template(folded, reasons)
    if template is None and inferred:
        if not quantities and count is None and not reasons:
            reasons.append(
                "Não foi possível reconhecer um circuito. Descreva a topologia (série, paralelo, "
                "divisor de tensão, interruptor ou iluminação de escada) e os valores, por "
                "exemplo «circuito em série com fonte de 12 V e resistências de 100 e 220 Ω»."
            )
        else:
            template = "series_dc"
            assumptions.append("Topologia não indicada: assumido um circuito em série.")

    if count is not None:
        if count < 1 or count > MAX_RESISTORS:
            reasons.append(f"O número de resistências tem de estar entre 1 e {MAX_RESISTORS}.")
        elif len(resistors) == 1 and count > 1:
            resistors = resistors * count
        elif resistors and len(resistors) != count:
            reasons.append(
                f"O texto indica {count} resistência(s) mas {len(resistors)} valor(es); "
                "indique um valor por resistência ou um único valor para todas."
            )
    if len(resistors) > MAX_RESISTORS:
        reasons.append(f"São suportadas no máximo {MAX_RESISTORS} resistências.")

    if reasons or template is None:
        raise UninterpretableTextError(reasons)

    if not voltages:
        voltages = [_DEFAULT_VOLTAGE_V]
        assumptions.append(f"Tensão da fonte não indicada: assumidos {_DEFAULT_VOLTAGE_V:g} V.")
    if _AC.search(folded):
        assumptions.append("Os circuitos gerados são de corrente contínua: a fonte é DC.")
    if not resistors:
        resistors = list(_DEFAULT_RESISTORS_OHM[template])
        if count is not None and template != "switch_circuit":
            resistors = [resistors[0]] * count
        assumptions.append(
            f"Valores das resistências não indicados: assumidos "
            f"{_join([_format_value(r, 'Ω') for r in resistors])}."
        )
    if _LAMP.search(folded):
        assumptions.append("As lâmpadas são representadas por resistências equivalentes.")

    voltage = voltages[0]
    parameters: dict[str, Any] = {"voltageV": voltage}
    if template == "switch_circuit":
        if len(resistors) > 1:
            raise UninterpretableTextError(
                ["O circuito com interruptor tem uma só carga; indique um único valor de Ω."]
            )
        is_open = bool(_OPEN.search(folded))
        if not is_open and not _CLOSED.search(folded):
            assumptions.append("Estado do interruptor não indicado: assumido fechado.")
        parameters |= {"loadOhm": resistors[0], "closed": not is_open}
    else:
        if template == "voltage_divider" and len(resistors) < 2:
            raise UninterpretableTextError(
                ["O divisor de tensão precisa de pelo menos duas resistências."]
            )
        parameters["resistorsOhm"] = resistors

    spec = get_template(template)
    try:
        params = spec.params_model.model_validate(parameters)
    except ValidationError as exc:
        raise InvalidParametersError(template, exc) from exc

    return Interpretation(
        template=template,
        parameters=params.model_dump(by_alias=True),
        summary=_summary(spec.title, template, parameters),
        assumptions=assumptions,
        params=params,
    )


def _interpret_staircase(text: str, folded: str) -> Interpretation:
    """`staircase_lighting`: só aceita V (rede), Hz, W (lâmpada) e A (disjuntor)."""
    reasons: list[str] = []
    assumptions: list[str] = []
    parameters: dict[str, Any] = {}
    for quantity in _quantities(text, reasons, frozenset(_STAIRCASE_UNITS)):
        if quantity.unit not in _STAIRCASE_UNITS:
            reasons.append(
                f"«{quantity.raw}»: na iluminação de escada indique a tensão da rede (V), a "
                "frequência (Hz), a potência da lâmpada (W) ou o disjuntor (A)."
            )
            continue
        key, _, label = _STAIRCASE_UNITS[quantity.unit]
        if key in parameters:
            reasons.append(f"O texto indica mais de um valor para a {label}.")
        parameters[key] = quantity.value
    if reasons:
        raise UninterpretableTextError(reasons)

    for unit, (key, default, label) in _STAIRCASE_UNITS.items():
        if key not in parameters:
            parameters[key] = default
            assumptions.append(f"{label.capitalize()} não indicada: assumidos {default:g} {unit}.")
    lit = bool(_LIT.search(folded)) and not _UNLIT.search(folded)
    if not lit and not _UNLIT.search(folded):
        assumptions.append("Comutadores na mesma posição: a lâmpada começa apagada.")
    parameters |= {"switch1ToL2": lit, "switch2ToL2": False}

    template = "staircase_lighting"
    spec = get_template(template)
    try:
        params = spec.params_model.model_validate(parameters)
    except ValidationError as exc:
        raise InvalidParametersError(template, exc) from exc
    data = params.model_dump(by_alias=True)
    state = "acesa" if lit else "apagada"
    summary = (
        f"{spec.title}: rede de {_format_value(data['voltageV'], 'V')} "
        f"{data['frequencyHz']:g} Hz, disjuntor de {data['breakerRatedA']:g} A, dois "
        f"comutadores e lâmpada de {_format_value(data['lampPowerW'], 'W')} ({state})."
    )
    return Interpretation(template, data, summary, assumptions, params)


def _summary(title: str, template: str, parameters: dict[str, Any]) -> str:
    parts = [f"fonte de {_format_value(parameters['voltageV'], 'V')}"]
    if template == "switch_circuit":
        state = "fechado" if parameters["closed"] else "aberto"
        parts.append(f"interruptor {state}")
        parts.append(f"carga de {_format_value(parameters['loadOhm'], 'Ω')}")
    else:
        values = [_format_value(r, "Ω") for r in parameters["resistorsOhm"]]
        noun = "resistência" if len(values) == 1 else "resistências"
        parts.append(f"{noun} de {_join(values)}")
    return f"{title}: {_join(parts)}."
