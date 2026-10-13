# @vcccircuitlab/web

Frontend do VCCCircuitLab: React + TypeScript + Vite, editor com React Flow (`@xyflow/react`) e estado em Zustand.

## Estrutura

```text
src/
├── editor/                # Canvas e lógica do editor
│   ├── EditorCanvas.tsx   # React Flow: grelha, pan, zoom, seleção, ferramenta de fio
│   ├── ComponentNodeView.tsx  # componente com pinos clicáveis (handles)
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
- Interação: arrastar o fundo faz pan; roda do rato/controlos fazem zoom; clique seleciona; Ctrl/⌘ + clique acrescenta à seleção; Shift + arrastar seleciona por caixa.

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
