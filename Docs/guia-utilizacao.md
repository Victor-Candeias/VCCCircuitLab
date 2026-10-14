# Guia de utilização — VCCCircuitLab

Este guia descreve como utilizar a aplicação **VCCCircuitLab** para desenhar, gerar, editar e
simular circuitos elétricos e eletrónicos: o editor manual, a geração automática por templates e
a simulação DC. Não é documentação de API nem de desenvolvimento — essa está em
[`apps/web/README.md`](../apps/web/README.md) e [`apps/api/README.md`](../apps/api/README.md).

> **Aviso:** os resultados de simulação são educativos e aproximados; não substituem projeto,
> inspeção ou ensaios de instalações reais por profissionais qualificados.

## 1. Editor manual

O editor ocupa o centro da aplicação: à esquerda a **paleta de componentes**, ao centro o
**canvas** (grelha, zoom e pan) e à direita o painel de **Simulação DC**.

### 1.1 Paleta e colocação de componentes

- A paleta é **pesquisável** e agrupada por categorias (fonte DC, resistência, interruptor,
  lâmpada, terra, instrumentos, etc.).
- **Arrastar e largar** (drag-and-drop) um componente da paleta para o canvas coloca-o com a
  âncora encaixada na grelha (snap-to-grid).
- Clicar num item da paleta (ou premir `Enter`/`Espaço` com o item em foco) adiciona o componente
  ao centro da vista atual, sem necessidade de arrastar.

### 1.2 Ferramenta de fio (ligações)

- Clicar num **terminal**, numa **junção** ou num **fio** existente começa um novo fio a partir
  desse ponto.
- Cliques seguintes no fundo do canvas fixam **pontos intermédios** (waypoints), sempre
  ortogonais.
- Clicar noutro terminal, junção ou fio **termina** o fio; terminar sobre um fio existente cria
  uma **junção explícita** nesse ponto (duas ligações que apenas se cruzam, sem junção, não ficam
  unidas na mesma rede).
- `Esc` cancela o fio em desenho; `Backspace` remove o último ponto intermédio fixado; o botão
  direito do rato sobre o fundo também cancela.

### 1.3 Seleção

- Clicar num componente ou junção seleciona-o (substitui a seleção anterior).
- `Ctrl`/`⌘` + clique acrescenta ou retira um elemento da seleção (multi-seleção).
- `Alt` + clique num fio seleciona-o (também combinável com `Ctrl`/`⌘` para acrescentar/retirar).
- `Shift` + arrastar no fundo do canvas faz **seleção por caixa**.
- Clicar no fundo do canvas limpa a seleção.

### 1.4 Mover, rodar, copiar/colar, apagar, desfazer/refazer

- **Mover:** arrastar um componente ou junção selecionado; ficam encaixados na grelha.
- **Rodar:** `R` roda a seleção 90° no sentido horário, `Shift+R` no sentido anti-horário
  (também disponível na barra de ferramentas do canvas).
- **Copiar/cortar/colar:** `Ctrl`/`⌘`+`C` copia, `Ctrl`/`⌘`+`X` corta, `Ctrl`/`⌘`+`V` cola a
  seleção.
- **Apagar:** `Delete` ou `Backspace` apaga a seleção atual (fora da ferramenta de fio e de
  campos de texto).
- **Desfazer/refazer:** `Ctrl`/`⌘`+`Z` desfaz; `Ctrl`/`⌘`+`Y` ou `Ctrl`/`⌘`+`Shift`+`Z` refaz.

A barra de ferramentas no canto superior direito do canvas repete estas ações (desfazer, refazer,
copiar, colar, apagar, rodar) para quem prefere clicar em vez de usar atalhos.

### 1.5 Atalhos de teclado — resumo

| Atalho | Ação |
|---|---|
| `R` / `Shift+R` | Rodar seleção 90° (horário / anti-horário) |
| `Ctrl`/`⌘`+`Z` | Desfazer |
| `Ctrl`/`⌘`+`Y` ou `Ctrl`/`⌘`+`Shift`+`Z` | Refazer |
| `Ctrl`/`⌘`+`C` / `X` / `V` | Copiar / cortar / colar |
| `Delete` / `Backspace` | Apagar seleção |
| `Ctrl`/`⌘` + clique | Acrescentar/retirar da seleção |
| `Alt` + clique num fio | Selecionar o fio |
| `Shift` + arrastar | Seleção por caixa |
| `Esc` (a desenhar um fio) | Cancelar o fio |
| `Backspace` (a desenhar um fio) | Remover o último ponto intermédio |

## 2. Projeto

O menu **Projeto**, no cabeçalho da aplicação, gere o ciclo de vida do circuito:

- **Novo:** começa um circuito vazio.
- **Abrir…:** carrega um ficheiro JSON canónico do computador; se o ficheiro for inválido, mostra
  os erros e **não** altera o circuito atual; se for válido mas tiver avisos, estes são mostrados
  depois de carregado.
- **Exemplos…:** lista de circuitos de exemplo prontos a abrir:
  - *Série: fonte, resistência e lâmpada*
  - *Fonte de 12 V e resistência*
  - *Paralelo com junções*
  - *Ramificado (ramos, ponte e cruzamento)*
  - *Divisor de tensão (R1 e R2 em série)*
  - *Interruptor e carga*
- **Guardar JSON:** descarrega o circuito atual como ficheiro JSON canónico.
- **Gerar…:** abre o diálogo de geração automática (secção seguinte).

**Confirmação ao descartar trabalho não guardado:** sempre que *Novo*, *Exemplos…* ou *Gerar…*
iriam substituir um circuito que já tem pelo menos um componente ou um fio, a aplicação pergunta
antes de descartar o circuito atual (ex.: "Descartar o circuito atual e abrir \<exemplo\>?"). Um
circuito vazio é substituído sem confirmação.

## 3. Geração automática

O botão **Gerar…** do menu Projeto abre um diálogo que pede à API (`POST
/api/v1/circuits/generate`) um circuito completo e editável a partir de um template e dos seus
parâmetros.

### 3.1 Templates disponíveis

| Template | Parâmetros apresentados no diálogo |
|---|---|
| **Série (fonte e resistores)** | *Tensão (V)*; *Resistências (Ω, separadas por vírgula)* |
| **Paralelo (fonte e resistores)** | *Tensão (V)*; *Resistências (Ω, separadas por vírgula)* |
| **Divisor de tensão** | *Tensão (V)*; *Resistências (Ω, separadas por vírgula, mínimo 2)* |
| **Interruptor e carga** | *Tensão (V)*; *Carga (Ω)*; caixa de verificação *Fechado* |

As resistências são indicadas como uma lista separada por vírgulas (ex.: `100, 220`). Ao escolher
outro template os campos voltam aos valores por omissão.

### 3.2 Fluxo e erros

1. Escolher o template na lista pendente.
2. Preencher os parâmetros (os campos têm valores por omissão razoáveis).
3. Clicar em **Gerar**.
4. Se os parâmetros forem rejeitados pela API, o diálogo mostra o título do erro e, quando
   aplicável, o campo exato (`pointer`) e a mensagem de cada problema, sem fechar o diálogo.
5. Se forem aceites, o circuito gerado substitui o circuito atual (com a mesma confirmação de
   descarte da secção 2, se o circuito atual não estava vazio) e o diálogo fecha.

Um circuito gerado automaticamente é um circuito **normal**: pode ser movido, religado, as suas
propriedades editadas, guardado em JSON e **simulado** como qualquer outro, tal como um desenhado
manualmente ou aberto de um exemplo.

## 4. Simulação DC

O painel **Simulação DC**, à direita do canvas, tem um botão **Simular** (desativado enquanto uma
simulação está a decorrer ou se o circuito não tiver componentes).

### 4.1 Resultados por componente

Uma tabela lista, para cada componente com resultado, a **tensão**, a **corrente** e a
**potência**. Convenção de sinais:

- Tensão e corrente são medidas do **1.º para o 2.º pino** do componente.
- **Potência negativa** significa que o componente **fornece** energia ao circuito (ex.: uma
  fonte), em vez de a consumir.

Clicar no identificador de um componente (ex. `R1`) seleciona-o no canvas, tal como clicar
diretamente nele.

### 4.2 Resultados por rede

Uma segunda tabela lista cada **rede** elétrica, a sua tensão e os terminais que a compõem.
Clicar numa rede **destaca-a** no canvas (as ligações e componentes dessa rede ficam
assinalados); clicar de novo remove o destaque.

### 4.3 Avisos e erros

- **Avisos** (ex.: situações válidas mas a assinalar) aparecem acima das tabelas de resultados,
  cada um com um botão **Mostrar** que seleciona os elementos referidos e destaca a primeira rede
  envolvida.
- **Erros** (circuito que não pôde ser simulado — por exemplo, terra em falta, rede flutuante ou
  matriz singular) substituem os resultados por uma mensagem de erro, também com **Mostrar**
  quando há elementos associados.
- Se o circuito for alterado depois da última simulação, o painel avisa que os resultados estão
  desatualizados e pede para simular de novo antes de os voltar a mostrar.

## Nota final

Lembre-se: **os resultados de simulação são educativos e aproximados; não substituem projeto,
inspeção ou ensaios de instalações reais por profissionais qualificados.** Use o VCCCircuitLab
para aprender e experimentar topologias de circuitos DC — não para validar instalações elétricas
reais.
