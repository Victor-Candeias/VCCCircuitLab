# @vcccircuitlab/web

Frontend do VCCCircuitLab: React + TypeScript + Vite, editor com React Flow (`@xyflow/react`) e estado em Zustand.

## Estrutura

```text
src/
├── api/                   # Cliente da API: simulate/validate, erros problem+json, timeout
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
│   ├── connectivity.ts    # redes derivadas de fios + junções (union-find, como a API)
│   ├── editing.ts         # apagar, copiar e colar (fragmentos com novos IDs)
│   ├── geometry.ts        # snap, rotação, âncora ↔ canto superior esquerdo
│   ├── catalog.ts         # catálogo de @vcccircuitlab/circuit-schema
│   └── demoCircuit.ts
├── project/               # Projeto: novo, abrir, guardar e gerar
│   ├── circuitJson.ts     # JSON canónico: serializar, validar (schema + integridade), ler ficheiro
│   ├── examples.ts        # circuitos de exemplo (fixtures de @vcccircuitlab/circuit-schema)
│   ├── generateTemplates.ts   # templates de geração (campos, valores por omissão, parsing)
│   ├── GenerateDialog.tsx # diálogo "Gerar…": template, parâmetros e chamada à API
│   └── ProjectMenu.tsx    # botões Novo / Abrir… / Exemplos / Guardar JSON / Gerar… e mensagens de erro
├── simulation/            # Simulação: painel de resultados, redes N1…, formatação SI
│   ├── SimulationPanel.tsx    # botão Simular, tabelas por componente e por rede, avisos e erros
│   ├── simulationStore.ts # Zustand: estado da última simulação e rede destacada
│   ├── nets.ts            # redes com os IDs da API e elementos a destacar no canvas
│   └── format.ts          # 40,9 mA, 1,5 kΩ… (prefixo SI, 3 algarismos significativos)
├── store/editorStore.ts   # Zustand: documento canónico, histórico (undo/redo) e estado de vista
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
- `deriveConnectivity` (`connectivity.ts`) agrupa os terminais em redes a partir dos fios e junções, pela mesma ordem do normalizador da API, e indica a rede de cada fio e junção.
- O exemplo **Ramificado** é o protótipo de validação do React Flow (§5.2): três ramos em paralelo, uma ponte, um cruzamento sem junção e uma junção de quatro fios. Ver as conclusões em `.maestru/specs/etapa-1/e1-08-spec.md`.

### Editar (desfazer, copiar/colar, apagar)

- **Desfazer / refazer**: `Ctrl+Z` desfaz; `Ctrl+Y` ou `Ctrl+Shift+Z` refaz (`⌘` no macOS), ou os botões ↶ ↷ da barra. Cada ação que altera o documento (adicionar, mover, rodar, ligar, apagar, colar) é um passo; um arrasto inteiro (um ou vários elementos) conta como um só. O histórico guarda até 100 passos e é limpo ao abrir ou criar um projeto. Uma ação nova descarta o que tinha sido desfeito.
- **Apagar**: `Delete` (ou `Backspace` fora do desenho de fios) ou o botão **Apagar** da barra apagam a seleção. Apagar um componente ou junção apaga também os fios ligados — não ficam fios soltos — e as junções que fiquem sem fios.
- **Selecionar fios**: `Alt` + clique num fio seleciona-o (`Ctrl+Alt` + clique acrescenta à seleção); o clique simples num fio continua a servir para desenhar ligações.
- **Copiar / cortar / colar**: `Ctrl+C`, `Ctrl+X`, `Ctrl+V` ou os botões da barra. Copia os componentes e junções selecionados e os fios entre eles; cada colagem recebe novos IDs estáveis (`R<n>`, `J<n>`, `W<n>` seguintes aos existentes), fica deslocada duas células na diagonal (após cortar, a primeira fica no mesmo sítio) e é selecionada.
- Os atalhos são ignorados enquanto se escreve num campo de texto.

### Projeto (abrir e guardar JSON)

- **Guardar JSON** descarrega o circuito como documento canónico (JSON Schema 1.0): chaves pela ordem do schema, indentação de 2 espaços, sem `nets` (é derivado e recalculado pela API) e sem estado de vista. O nome do ficheiro vem do nome do circuito (`circuito-serie.json`).
- **Abrir…** lê um ficheiro `.json` local (máx. 5 MB) e valida-o antes de substituir o circuito atual: JSON Schema 1.0 (Ajv, draft 2020-12) e regras de integridade de que o editor depende — IDs únicos em todo o documento, tipos e pinos do catálogo, extremidades de fios existentes e fios não ligados a si próprios. Se houver erros, aparecem numa mensagem (com o caminho JSON) e o circuito atual não é alterado. Um `nets` no ficheiro é ignorado (com aviso). Depois de abrir, a vista enquadra o circuito.
- **Novo** começa um circuito vazio; **Exemplos…** abre um circuito de exemplo (série, paralelo com junções, ramificado). Ambos pedem confirmação se o circuito atual não estiver vazio.
- **Gerar…** abre um diálogo com os templates da API (série, paralelo, divisor de tensão, interruptor e carga — ver `apps/api/README.md`), pede os parâmetros (tensão, lista de resistências, carga, estado do interruptor) e envia-os a `POST /api/v1/circuits/generate`. O circuito devolvido (sem `nets`, recalculados no editor) substitui o atual, com confirmação se este não estiver vazio. Parâmetros inválidos (localmente, ou devolvidos pela API) aparecem no diálogo sem fechar.
- Round-trip: exportar e voltar a importar dá o mesmo documento (topologia, parâmetros e geometria) e o mesmo ficheiro.

### Simulação (API)

- **Simular** envia o circuito (documento canónico, sem `nets`) para `POST /api/v1/circuits/simulate` e mostra, para cada componente, a tensão, a corrente e a potência (convenção passiva: do 1.º para o 2.º pino; potência negativa = fornece energia) e a tensão de cada rede em relação à terra. Os valores usam prefixos SI e 3 algarismos significativos (`40,9 mA`).
- As redes têm os IDs da API (`N1`, `N2`… pela ordem do normalizador). Clicar numa rede destaca no canvas os seus fios, junções e terminais; clicar num componente da tabela seleciona-o.
- Avisos da API aparecem acima dos resultados; erros (`application/problem+json`) aparecem com a mensagem e o código de cada erro, e **Mostrar** seleciona os elementos citados (e destaca a rede citada). Falhas de rede, timeout (15 s) e respostas inesperadas também são mostradas.
- Os resultados correspondem ao circuito simulado: se o circuito mudar, o painel pede uma nova simulação (desfazer até ao mesmo circuito volta a mostrá-los). Uma nova simulação cancela a anterior.
- **URL da API**: `VITE_API_BASE_URL` (ver `.env.example`), usada no build — p. ex. `VITE_API_BASE_URL=https://api.exemplo.pt`. Vazia (omissão), os pedidos vão para a mesma origem e o `vite dev`/`vite preview` encaminham `/api` para `API_PROXY_TARGET` (por omissão `http://127.0.0.1:8000`) — assim o editor funciona também quando aberto noutra máquina da rede, sem CORS. Não colocar segredos em variáveis `VITE_*`.

## Comandos (a partir da raiz do repositório)

```bash
pnpm install
pnpm --filter @vcccircuitlab/web dev       # servidor de desenvolvimento (/api → 127.0.0.1:8000)
pnpm --filter @vcccircuitlab/web build     # tsc -b + vite build → apps/web/dist
pnpm --filter @vcccircuitlab/web lint
pnpm --filter @vcccircuitlab/web test      # Vitest + Testing Library (jsdom)
pnpm --filter @vcccircuitlab/web test:watch
pnpm --filter @vcccircuitlab/web preview
```

## GitHub Pages

O `base` do Vite é `/VCCCircuitLab/` por omissão (site servido em `https://<utilizador>.github.io/VCCCircuitLab/`).
Para um domínio próprio na raiz, definir `BASE_PATH=/` no build.
