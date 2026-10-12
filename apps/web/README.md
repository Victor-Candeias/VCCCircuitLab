# @vcccircuitlab/web

Frontend do VCCCircuitLab: React + TypeScript + Vite, editor com React Flow (`@xyflow/react`) e estado em Zustand.

## Estrutura

```text
src/
├── editor/                # Canvas e lógica do editor
│   ├── EditorCanvas.tsx   # React Flow: grelha, pan, zoom, seleção
│   ├── ComponentNodeView.tsx
│   ├── flowNodes.ts       # documento canónico → nós do React Flow
│   ├── geometry.ts        # snap, rotação, âncora ↔ canto superior esquerdo
│   ├── catalog.ts         # catálogo de @vcccircuitlab/circuit-schema
│   └── demoCircuit.ts
├── store/editorStore.ts   # Zustand: documento canónico + estado de vista
└── test/                  # setup do Vitest e mocks do React Flow para jsdom
```

## Editor

- O store guarda o **documento canónico** (`CircuitDocument`) separado do **estado de vista** (seleção). Os nós do React Flow são derivados do documento; as alterações do canvas voltam ao store.
- `Component.position` é o **centro** do símbolo (âncora); o tamanho vem do catálogo e roda com o componente. O snap à grelha (20) é aplicado à âncora, para que os pinos fiquem na grelha.
- Interação: arrastar o fundo faz pan; roda do rato/controlos fazem zoom; clique seleciona; Ctrl/⌘ + clique acrescenta à seleção; Shift + arrastar seleciona por caixa.

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
