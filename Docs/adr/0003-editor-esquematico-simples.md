# 0003. Editor esquemático simples

- **Estado:** Aceite
- **Data:** 2026-10-12

## Contexto

Ferramentas CAD elétricas oferecem fidelidade rigorosa (folhas, cotas, bibliotecas normativas), mas o seu custo de implementação é elevado e não é necessário para aprendizagem e simulação de circuitos simples.

## Decisão

Construir um **editor esquemático simples** sobre React Flow (`@xyflow/react`) com símbolos SVG próprios: grelha, snap, rotação em múltiplos de 90°, fios ortogonais e junções explícitas — sem pretensão de fidelidade CAD.

## Consequências

- React Flow não é um CAD elétrico: é preciso implementar regras de ligação por pino, junções, cruzamentos sem ligação, roteamento ortogonal e exportação.
- Deve-se prototipar cedo circuitos ramificados (E1-08) para confirmar a adequação do React Flow.
- O desenho é separado do circuito elétrico: cruzamentos visuais não criam ligações.
