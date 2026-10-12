# @vcccircuitlab/circuit-schema

JSON Schema **1.0** do documento canónico de circuito do VCCCircuitLab (`schema/circuit.schema.json`, draft 2020-12) e tipos TypeScript gerados (`src/circuit.ts`).

```ts
import type { CircuitDocument } from '@vcccircuitlab/circuit-schema';
import schema from '@vcccircuitlab/circuit-schema/circuit.schema.json';
```

## Comandos

```bash
pnpm --filter @vcccircuitlab/circuit-schema generate   # regenerar src/circuit.ts a partir do schema
pnpm --filter @vcccircuitlab/circuit-schema test       # validar fixtures + tipos sincronizados + tsc
```

`src/circuit.ts` é gerado — não editar à mão. O teste falha se não estiver sincronizado com o schema.

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

## Regras fora do JSON Schema

Verificadas pelo validador do backend (E2-02), não pelo schema:

- unicidade de IDs no documento;
- referências de fios/redes a componentes, pinos e junções existentes;
- `from` ≠ `to` num fio;
- consistência de `nets` com `wires`/`junctions`;
- propriedades exigidas e limites de valores por tipo de componente (catálogo, E0-08).
