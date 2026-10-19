# @vcccircuitlab/circuit-schema

JSON Schema **1.0** do documento canónico de circuito do VCCCircuitLab (`schema/circuit.schema.json`, draft 2020-12), schema do catálogo de componentes (`schema/catalog.schema.json`) e tipos TypeScript gerados (`src/circuit.ts`, `src/catalog.ts`).

```ts
import type { CircuitDocument, ComponentCatalog } from '@vcccircuitlab/circuit-schema';
import schema from '@vcccircuitlab/circuit-schema/circuit.schema.json';
import catalogFixture from '@vcccircuitlab/circuit-schema/fixtures/catalog.json'; // só para testes
import ramificado from '@vcccircuitlab/circuit-schema/examples/ramificado.json'; // fixtures válidas
```

## Comandos

```bash
pnpm --filter @vcccircuitlab/circuit-schema generate   # regenerar src/circuit.ts e src/catalog.ts a partir dos schemas
pnpm --filter @vcccircuitlab/circuit-schema test       # validar fixtures + catálogo + tipos sincronizados + tsc
```

As fixtures válidas (`test/fixtures/valid/*.json`) são também exportadas como exemplos (`./examples/*.json`): o editor web abre-as no menu Exemplos e os testes da API usam-nas. `ramificado.json` é o protótipo de circuito ramificado do editor (três ramos, ponte, cruzamento sem junção, junção de quatro fios).

`src/circuit.ts` e `src/catalog.ts` são gerados — não editar à mão. O teste falha se não estiverem sincronizados com os schemas.

## Estrutura do documento

| Campo | Obrigatório | Descrição |
|---|---|---|
| `schemaVersion` | sim | `"1.0"` |
| `id`, `name` | sim | Identificação do circuito |
| `units` | sim | `"SI"` |
| `components` | sim | Componentes com `id`, `type`, `position`, `rotation`, `properties`, `pins` |
| `junctions` | não | Junções explícitas fio-a-fio (`id`, `position`) |
| `wires` | sim | Fios `from` → `to` com `waypoints` |
| `nets` | não | Redes derivadas (cache) |

## Convenções

### Identificadores

- `ElementId` (componentes, junções, fios, redes): `^[A-Za-z][A-Za-z0-9_-]{0,63}$`, sensível a maiúsculas.
- `PinId`: `^[A-Za-z][A-Za-z0-9_]{0,31}$`, único dentro do componente.
- O `.` é **reservado** como separador de terminal e não pode aparecer em IDs.
- IDs são **estáveis** (não mudam com a posição gráfica) e **únicos em todo o documento**, entre todos os tipos de elemento.

### Terminais e extremidades de fios

- Terminal: `<componentId>.<pinId>` (ex.: `R1.a`, `V1.positive`).
- Extremidade de fio (`from`/`to`): um terminal ou o `id` de uma junção (sem `.`).

### Conectividade (fonte de verdade)

- **`wires` + `junctions` são a fonte de verdade** da conectividade elétrica e da geometria.
- Dois fios só ficam ligados se partilharem uma extremidade (terminal ou junção). **Cruzamentos visuais sem junção não ligam redes.**
- Vários fios no mesmo terminal ficam ligados nesse terminal.
- `nets` é **derivado** pelo normalizador (union-find) a partir dos fios. É opcional; se existir e for inconsistente com os fios, o documento é rejeitado — nunca é aceite só por aparecer no JSON.

### Geometria

- Coordenadas em unidades de canvas (px a zoom 1), eixo `y` para baixo.
- `position` é o ponto de ancoragem do símbolo.
- `rotation` em **graus, sentido horário**, em torno de `position`: `0 | 90 | 180 | 270`.
- `waypoints` são os pontos intermédios do traçado, excluindo as extremidades.

### Propriedades e unidades

- Unidades SI; o nome da propriedade inclui o sufixo da unidade, em camelCase: `voltageV`, `resistanceOhm`, `currentA`, `powerW`.
- Valores tipados: `number` ou `boolean` (estados, ex.: `closed`). Strings não são aceites.

### Versionamento

- `schemaVersion` identifica a versão do documento. Alterações incompatíveis exigem nova versão e uma migração.

## Catálogo de componentes

O catálogo de componentes vem da API (`GET /api/v1/components`, coleção `templates` do MongoDB — F2-10/F2-11); não há cópia estática de produção neste pacote. `test/fixtures/catalog.json` (exportado como `./fixtures/catalog.json`) é a fixture de referência usada pelos testes (deste pacote e do `apps/web`), validada por `schema/catalog.schema.json`. O catálogo separa, por tipo de componente, o **símbolo**, os **terminais**, a **validação de propriedades** e o **modelo elétrico** (§4.1 da arquitetura).

| Tipo | Prefixo | Pinos | Propriedades (omissão) | Modelo elétrico |
|---|---|---|---|---|
| `dc_voltage_source` | `V` | `positive`, `negative` | `voltageV` = 12 (0 < V ≤ 120) | `dc_voltage_source` |
| `dc_current_source` | `I` | `positive`, `negative` | `currentA` = 0.1 (0 < A ≤ 10) | `dc_current_source` |
| `resistor` | `R` | `a`, `b` | `resistanceOhm` = 1000 (> 0) | `resistor` |
| `switch` | `S` | `a`, `b` | `closed` = false | `ideal_switch` |
| `lamp` | `H` | `a`, `b` | `ratedVoltageV` = 12 (0 < V ≤ 120), `ratedPowerW` = 5 (> 0) | `resistive_lamp` (R = V²/P) |
| `ground` | `GND` | `gnd` | — | `ground` |

Convenções do catálogo:

- **Grelha**: `gridSize` = 20 unidades de canvas; as posições dos pinos são múltiplos da grelha.
- **Pinos**: `position` é relativa a `Component.position` com `rotation` = 0; o editor aplica a rotação (horária) para obter a posição absoluta. Os pinos ficam dentro de `size` (centrado na âncora).
- **Polaridade**: na fonte de tensão, `positive` está `voltageV` acima de `negative`; na fonte de corrente, a corrente entra por `negative` e sai por `positive` para o circuito externo.
- **Prefixos de ID**: novas instâncias recebem `<idPrefix><n>` (ex.: `R1`, `R2`); `H` é usado para lâmpadas para não colidir com `L` (bobinas, fase futura).
- **Propriedades**: `number` (com `unit`, `default` e limites `minimum`/`maximum`/`exclusiveMinimum`/`exclusiveMaximum`, com a semântica do JSON Schema) ou `boolean`. O `default` respeita os limites.
- **Modelo elétrico**: `simulationModel` = `null` marca um componente que pode ser desenhado mas é **não suportado pelo solver**.
- Os testes verificam que as fixtures de circuito só usam tipos, pinos e propriedades válidos do catálogo.
- A API (`apps/api`) usa uma cópia em `apps/api/app/circuit/data/components.json`, que tem de ser atualizada sempre que o catálogo muda. Um teste da API compara as duas versões.

## Regras fora do JSON Schema

Verificadas pelo validador do backend (E2-02), não pelo schema:

- unicidade de IDs no documento;
- referências de fios/redes a componentes, pinos e junções existentes;
- `from` ≠ `to` num fio;
- consistência de `nets` com `wires`/`junctions`;
- propriedades exigidas e limites de valores por tipo de componente (definidos no catálogo de componentes).
