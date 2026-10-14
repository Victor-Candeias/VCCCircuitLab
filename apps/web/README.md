# @vcccircuitlab/web

Frontend do VCCCircuitLab: React + TypeScript + Vite, editor com React Flow (`@xyflow/react`) e estado em Zustand.

## Estrutura

```text
src/
├── components/symbols/    # Símbolos SVG IEC 60617
│   ├── ComponentSymbol.tsx    # caixa SVG centrada na âncora, com rotação
│   ├── iecSymbols.tsx     # desenho de cada símbolo (coordenadas locais)
│   └── symbolIds.ts       # IDs desenhados (`ComponentDefinition.symbol`)
├── editor/                # Canvas e lógica do editor
│   ├── EditorCanvas.tsx   # React Flow: grelha, pan, zoom, seleção, fio, largar e rodar
│   ├── ComponentPalette.tsx   # paleta pesquisável por categoria (arrastar ou clicar)
│   ├── palette.ts         # agrupamento e pesquisa do catálogo
│   ├── placement.ts       # novas instâncias (ID, propriedades, snap) e rotação
│   ├── ComponentNodeView.tsx  # símbolo IEC do componente com pinos clicáveis (handles)
│   ├── JunctionNodeView.tsx   # junção explícita (ponto cheio)
│   ├── WireEdgeView.tsx   # fio ortogonal
│   ├── flowNodes.ts       # documento canónico → nós e arestas do React Flow
│   ├── wiring.ts          # posições de pinos, traçado ortogonal, fios e junções
│   ├── geometry.ts        # snap, rotação, âncora ↔ canto superior esquerdo
│   ├── catalog.ts         # catálogo de @vcccircuitlab/circuit-schema
│   └── demoCircuit.ts
├── store/editorStore.ts   # Zustand: documento canónico + estado de vista
└── test/                  # setup do Vitest e mocks do React Flow para jsdom
```

## Editor

- O store guarda o **documento canónico** (`CircuitDocument`) separado do **estado de vista** (seleção, fio em desenho). Os nós e fios do React Flow são derivados do documento; as alterações do canvas voltam ao store.
- `Component.position` é o **centro** do símbolo (âncora); o tamanho vem do catálogo e roda com o componente. O snap à grelha (20) é aplicado à âncora, para que os pinos fiquem na grelha.
- Interação: arrastar o fundo faz pan; roda do rato/controlos fazem zoom; clique seleciona; Ctrl/⌘ + clique acrescenta à seleção; Shift + arrastar seleciona por caixa; arrastar um componente move-o (com snap).

### Paleta e rotação

- A paleta (à esquerda) mostra o catálogo agrupado por categoria (Fontes, Passivos, Interruptores, Cargas, Referência), com o símbolo IEC de cada componente. A pesquisa ignora maiúsculas e acentos e exige todas as palavras (nome, tipo, prefixo do ID, descrição ou categoria).
- **Adicionar**: arrastar um item para o canvas (a âncora fica no ponto largado, encaixada na grelha) ou clicar/Enter no item (centro da vista). Se a âncora já estiver ocupada por outro componente, desloca-se uma célula na diagonal. O novo componente fica selecionado, com rotação 0, as propriedades por omissão do catálogo e o próximo ID livre com o prefixo do catálogo (`R2`, `GND2`…).
- **Rodar**: `R` roda os componentes selecionados 90° no sentido horário e `Shift+R` no sentido anti-horário (também pelos botões no canto superior direito). Cada componente roda em torno da própria âncora e os pinos continuam na grelha; os fios ligados são redesenhados ortogonalmente. As teclas não atuam enquanto se escreve num campo.

### Símbolos IEC

- Cada componente é desenhado com o símbolo IEC 60617 indicado em `ComponentDefinition.symbol`: fonte de tensão (círculo atravessado pelo condutor, com `+`/`−`), fonte de corrente (círculo com traço perpendicular e seta no sentido da corrente), resistência (retângulo), interruptor (contacto de fecho, aberto ou fechado conforme `closed`), lâmpada (círculo com cruz) e terra.
- Os símbolos são desenhados em coordenadas locais (origem na âncora, rotação 0, unidades do catálogo) e os condutores terminam exatamente nas posições dos pinos do catálogo. A rotação SVG é a mesma de `rotateOffset`, por isso pinos e desenho rodam juntos; os sinais de polaridade ficam sempre na vertical.
- Para acrescentar um símbolo: desenhá-lo em `iecSymbols.tsx`, juntar o ID a `SYMBOL_IDS` e ao `switch` de `IecSymbol`. Os testes verificam que cada símbolo do catálogo existe e que cada pino é a extremidade de um condutor.
- Tipos fora do catálogo aparecem como marcador de erro (caixa tracejada); símbolos do catálogo ainda sem desenho aparecem como caixa tracejada vermelha.

### Ligações (fios e junções)

- **Desenhar um fio**: clicar num terminal (pino), numa junção ou num fio para começar; cada clique no fundo fixa um ponto intermédio (encaixado na grelha, com canto ortogonal); clicar noutro terminal, junção ou fio para terminar. `Esc` (ou botão direito no fundo) cancela; `Backspace` remove o último ponto.
- **Junções explícitas**: começar ou terminar um fio _sobre_ um fio existente divide-o em dois e cria uma junção (`J<n>`), desenhada como um ponto cheio. As junções podem ser arrastadas (com snap).
- **Cruzamentos não ligam**: um fio que passa por cima de outro sem junção nem terminal comum não fica ligado; a conectividade vem apenas das extremidades (`from`/`to`) dos fios.
- Os fios são sempre desenhados ortogonais: se um componente for movido e um troço ficar diagonal, é desenhado com um canto (horizontal primeiro), sem alterar o documento.
- Ligações inválidas (um terminal a si próprio, um fio a si próprio) são ignoradas. Os novos IDs (`W<n>`, `J<n>`) são únicos em todo o documento.

## Comandos (a partir da raiz do repositório)

```bash
pnpm install
pnpm --filter @vcccircuitlab/web dev       # servidor de desenvolvimento
pnpm --filter @vcccircuitlab/web build     # tsc -b + vite build → apps/web/dist
pnpm --filter @vcccircuitlab/web lint
pnpm --filter @vcccircuitlab/web test      # Vitest + Testing Library (jsdom)
pnpm --filter @vcccircuitlab/web test:watch
pnpm --filter @vcccircuitlab/web preview
```

## GitHub Pages

O `base` do Vite é `/VCCCircuitLab/` por omissão (site servido em `https://<utilizador>.github.io/VCCCircuitLab/`).
Para um domínio próprio na raiz, definir `BASE_PATH=/` no build.
