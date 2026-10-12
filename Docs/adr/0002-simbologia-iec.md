# 0002. Simbologia IEC europeia

- **Estado:** Aceite
- **Data:** 2026-10-12

## Contexto

Os símbolos elétricos diferem entre normas (IEC 60617 na Europa, ANSI/IEEE nos EUA). O público-alvo inicial é europeu (Portugal) e a interface deve ser coerente.

## Decisão

Usar a **simbologia IEC europeia** como padrão em todos os símbolos SVG do editor e nas exportações. A simbologia ANSI poderá ser suportada mais tarde como opção de apresentação.

## Consequências

- Os símbolos SVG são desenhados à medida (ex.: resistência retangular IEC).
- O catálogo separa `symbol` de `type`/`simulationModel`, permitindo acrescentar variantes ANSI sem alterar o modelo de dados.
