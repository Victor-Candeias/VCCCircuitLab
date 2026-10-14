---
maestru: "0.4"
type: work-spec
id: e1-08-spec
title: "E1-08 — Protótipo de circuitos ramificados"
template: implementation-plan-v1
work-item: etapa-1/E1-08
owner: developer
created: 2026-10-14
---

# E1-08 — Protótipo de circuitos ramificados

## Overview

Validar cedo (§5.2) que o React Flow serve de editor esquemático com circuitos de vários ramos e junções, antes de construir mais funcionalidades em cima dele. O protótipo é um circuito de referência partilhado pelo pacote do schema, pelo editor e pela API. A conectividade no browser é derivada como na API.

Decisões:

- **Circuito `ramificado`** (`packages/circuit-schema/test/fixtures/valid/ramificado.json`). Tem 9 V, um interruptor e três ramos em paralelo: R1; R2 + H1 em série; R3. Tem também uma ponte R4 do nó R2/H1 para a terra, cinco junções (J3 liga quatro fios) e um **cruzamento sem junção** (W8 × W11 em (540, 240)). Está todo na grelha e com troços já ortogonais.
  - Como fixture válida, é verificado automaticamente pelo schema e pelo catálogo (testes do pacote) e pela normalização da API.
- **Exemplos**: o pacote exporta as fixtures válidas como `@vcccircuitlab/circuit-schema/examples/*.json`. O editor oferece-as num seletor "Exemplos…" (`src/project/examples.ts`) junto do circuito de demonstração, com confirmação antes de substituir um circuito não vazio.
- **`deriveConnectivity`** (`src/editor/connectivity.ts`) é um union-find sobre terminais e junções. Dá redes com terminais pela mesma ordem do `build_nets` da API, mais a rede de cada fio e de cada junção.
  - Servirá para realçar redes com os resultados da simulação (E2-07).
  - O `nets` do documento nunca é usado.

### Conclusões da avaliação do React Flow

Adequado para o MVP:

- Nós personalizados com símbolos SVG e um handle por pino.
- Junções como nós próprios.
- Arestas personalizadas com traçado ortogonal calculado a partir do documento.
- Seleção, pan, zoom e drag funcionam com o documento canónico como fonte de verdade.
- Os cruzamentos sem junção não ligam, porque a conectividade vem só das extremidades dos fios.
- Mover uma junção redesenha os fios ligados.
- Ligar um fio novo a um nó com quatro fios ou ao meio de um ramo (nova junção) funciona.

Escala, medida com escadas geradas, `vite build` + `vite preview` e Chromium headless:

| Escada | Nós / fios | Carregar (inclui validação Ajv) | Arrastar |
|--------|------------|---------------------------------|----------|
| 100 ramos | 302 / 401 | ≈ 1,2 s | ≈ 27 ms por passo |
| 300 ramos | 902 / 1201 | ≈ 3,1 s | ≈ 27 ms por passo |

Os circuitos didáticos do MVP (dezenas de componentes) estão muito abaixo destes valores.

Limitações conhecidas (o React Flow não é um CAD elétrico):

- Não há encaminhamento automático com desvio de obstáculos. Depois de mover componentes, um fio pode passar por cima de símbolos ou sobrepor-se a outro, porque o canto é sempre horizontal-primeiro.
- Os waypoints não são arrastáveis.
- As arestas não são selecionáveis (`selectable: false`). Apagar fios fica para E1-06.
- Em circuitos muito grandes, considerar `onlyRenderVisibleElements` e memorização dos nós.

## Implementation

1. `packages/circuit-schema/test/fixtures/valid/ramificado.json` e o export `./examples/*.json` em `package.json`. Atualizar o README do pacote.
2. `apps/web/src/editor/connectivity.ts`: `deriveConnectivity`.
3. `apps/web/src/project/examples.ts`: `CIRCUIT_EXAMPLES`. Em `ProjectMenu.tsx` e `project.css`: o seletor "Exemplos…".
4. Testes web:
   - `connectivity.test.ts`: redes iguais às da API, cruzamento separado, fios e junções, singulares, fio a meio de um ramo junta redes, extremidades inexistentes.
   - `examples.test.ts`: exemplos válidos e com round-trip; desenho na grelha e ortogonal; cruzamento; nós e arestas do React Flow.
   - `EditorCanvas.test.tsx`: desenha 8 componentes, 5 junções e 16 fios, e liga R4.b a J1.
   - `ProjectMenu.test.tsx`: seletor de exemplos.
5. Testes da API:
   - `ramificado` em `test_fixtures_are_valid`.
   - `test_branched_prototype`: redes, valores calculados à mão (H1 ‖ R4 em série com R2), KCL no nó intermédio e corrente total.
6. `apps/web/README.md`: estrutura, exemplos e conectividade.

Verificação:

- `pnpm --filter @vcccircuitlab/web test` (139 testes), `lint`, `build` e `pnpm format:check`.
- Pacote: 45 testes. API: `pytest` (252 testes), `ruff check` e `ruff format --check`.
- No browser (Chromium headless): exemplo desenhado sem erros na consola, arrastar J2 redesenha os fios, e medições de escala.

## Impacted Files

| File | Action | Purpose |
|------|--------|---------|
| `packages/circuit-schema/test/fixtures/valid/ramificado.json` | create | Circuito ramificado de referência |
| `packages/circuit-schema/package.json` | modify | Export `./examples/*.json` |
| `packages/circuit-schema/README.md` | modify | Documentar os exemplos |
| `apps/web/src/editor/connectivity.ts` | create | Redes derivadas dos fios |
| `apps/web/src/editor/connectivity.test.ts` | create | Testes da conectividade |
| `apps/web/src/project/examples.ts` | create | Circuitos de exemplo |
| `apps/web/src/project/examples.test.ts` | create | Validade, desenho e React Flow do protótipo |
| `apps/web/src/project/ProjectMenu.tsx` | modify | Seletor de exemplos |
| `apps/web/src/project/ProjectMenu.test.tsx` | modify | Teste do seletor |
| `apps/web/src/project/project.css` | modify | Estilo do seletor |
| `apps/web/src/editor/EditorCanvas.test.tsx` | modify | Canvas com o circuito ramificado |
| `apps/api/tests/test_api_circuits.py` | modify | Simulação do protótipo |
| `apps/api/tests/test_circuit_validate.py` | modify | Fixture válida |
| `apps/web/README.md` | modify | Documentação |
