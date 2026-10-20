---
maestru: "0.4"
type: work-spec
id: f2-05-spec
title: "F2-05 — Importação/exportação SPICE"
template: implementation-plan-v1
work-item: fase-2/F2-05
owner: developer
created: 2026-10-20
---

# F2-05 — Importação/exportação SPICE

## Overview

Tradutor bidirecional entre o documento canónico (JSON 1.0) e netlists SPICE, no backend (`app/spice/exchange.py`), com dois endpoints e botões no menu Projeto do editor.

- **Exportação:** circuito validado (regras da transitória) → netlist com `.op`, legível pelo ngspice. Elementos R/C/L/V/I/D/Q e `.model` iguais aos parâmetros do solver interno. Depois de `.end`, o documento completo num comentário `*@vcccircuitlab {…}`.
- **Importação:**
  - Se o documento embutido corresponder aos elementos e modelos da netlist (assinatura normalizada), devolve-o sem perdas.
  - Caso contrário, infere os componentes:
    - Elementos: R, C, L, V/I DC, D e Q com `.model`. Os LEDs são reconhecidos pelo nome do modelo.
    - Desenho: grelha de 4 colunas, com terra por baixo e um fio em cadeia por nó.
    - Avisos: diretivas ignoradas e modelos aproximados.
- **Erros:** 422 `invalid-netlist` / `INVALID_NETLIST`. Cada erro tem um código e começa por `Linha N:`. Tudo o que não é suportado é erro: subcircuitos, fontes não DC, fontes controladas, `.include`/`.lib`/`.param`.
- **Fora do âmbito:**
  - `.subckt`, fontes PULSE/SIN/PWL e elementos controlados.
  - Ler interruptores e instrumentos de uma netlist estranha: uma `V … 0` dá um amperímetro.
  - Execução da netlist (só é lida).

## Implementation

### Fase 1 — Tradutor (backend)

| Step | Action |
|------|--------|
| 1.1 | `export_netlist(document, catalog)`: validação, nomes SPICE únicos (letra + id), nós = ids das redes (terra `0`), díodo com `IS` derivado de VF/IF e `N=2`, transístor com `BR=1`, documento embutido após `.end`. |
| 1.2 | `_parse`: linhas lógicas (`+`, comentários `*`, `;`, ` $ `), `.end`, blocos `.control`, diretivas ignoradas (aviso), proibidas (erro), `.model` com parâmetros, assinatura normalizada. |
| 1.3 | `parse_value`: sufixos SPICE em `Decimal` (`100n` → 1e-07 exato). |
| 1.4 | `_Builder.translate`: R/C/L (`IC=`), V/I DC (sinal → troca de pinos; `V 0` → amperímetro; `I 0` omitida), D (LED se o modelo contém `led`; VF = N·Vt·ln(1+IF/IS)), Q (substrato opcional, BF/IS). |
| 1.5 | `_Builder.build`: ids saneados e únicos, grelha 4 colunas, terra por baixo, fios em cadeia por nó. Erros de parsing e de elementos juntos, ordenados por linha (máx. 20). |
| 1.6 | `import_netlist`: documento embutido se a assinatura coincidir com a da sua reexportação; senão inferência + aviso `EMBEDDED_CIRCUIT_IGNORED`; `issues` = relatório do validador. |

### Fase 2 — API

| Step | Action |
|------|--------|
| 2.1 | `InvalidNetlistError` → handler 422 `invalid-netlist` (`app/problems.py`, `ApiErrorCode.INVALID_NETLIST`). |
| 2.2 | `POST /api/v1/circuits/export/spice` (`CircuitDocument` → `{netlist}`) e `POST /api/v1/circuits/import/spice` (`{netlist}` ≤ 256 KiB, `extra=forbid` → `{circuit, warnings, issues}`), protegidos pela sessão como o resto do router. |

### Fase 3 — Editor

| Step | Action |
|------|--------|
| 3.1 | `exportSpice` / `importSpice` em `api/client.ts` (com validação da resposta) e `SpiceImportResult` em `api/types.ts`. |
| 3.2 | `ProjectMenu`: «Exportar SPICE» (descarrega `<slug>.cir`, `text/plain`) e «Importar SPICE…» (input `.cir/.sp/.spice/.net/.txt`, limite 256 KiB, circuito revalidado com `parseCircuit`, avisos/erros no aviso do menu). |

### Verificação

- `tests/test_spice_exchange.py` (76 testes):
  - Sufixos.
  - Exportação: linhas, IS do díodo, nomes únicos, componentes omitidos, fonte de corrente invertida.
  - Ida e volta exata em todas as fixtures válidas.
  - Inferência sem o documento embutido, simulada em DC igual ao original em todas as fixtures.
  - Netlist escrita à mão com tudo o que é suportado.
  - Erros com o número da linha.
  - Endpoints.
- `tests/test_spice_ngspice.py`: as netlists exportadas correm no ngspice real (CI) e dão as mesmas tensões nas resistências que o MNA.
- Web: `client.test.ts` e `ProjectMenu.test.tsx` (exportar, erro de exportação, importar com avisos, netlist inválida, ficheiro demasiado grande).
- Comandos: `pytest`, `ruff`, `tsc -b`, `eslint`, `prettier`, `vitest`, `vite build`.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/spice/exchange.py` | create | Tradutor netlist ↔ JSON |
| `apps/api/app/problems.py` | modify | `INVALID_NETLIST` e handler `invalid-netlist` |
| `apps/api/app/routes/circuits.py` | modify | Endpoints `export/spice` e `import/spice` |
| `apps/api/tests/test_spice_exchange.py` | create | Testes do tradutor e dos endpoints |
| `apps/api/tests/test_spice_ngspice.py` | modify | Netlists exportadas no ngspice real (CI) |
| `apps/api/README.md` | modify | Secção «Importação/exportação SPICE», endpoints e erros |
| `apps/web/src/api/client.ts` | modify | `exportSpice`, `importSpice` |
| `apps/web/src/api/types.ts` | modify | `SpiceImportResult` |
| `apps/web/src/api/client.test.ts` | modify | Testes do cliente |
| `apps/web/src/project/ProjectMenu.tsx` | modify | Botões «Exportar SPICE» e «Importar SPICE…» |
| `apps/web/src/project/ProjectMenu.test.tsx` | modify | Testes do menu |
| `README.md` | modify | Parágrafo F2-05 |
