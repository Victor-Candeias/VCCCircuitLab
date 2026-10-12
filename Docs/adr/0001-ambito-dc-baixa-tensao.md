# 0001. Âmbito do MVP: apenas DC de baixa tensão

- **Estado:** Aceite
- **Data:** 2026-10-12

## Contexto

O simulador destina-se a fins educativos. Análise AC/transitória, semicondutores e instalações de 230/400 V exigem modelos, validação e avisos de segurança que não cabem num MVP, e resultados errados nesses domínios podem induzir decisões perigosas.

## Decisão

O MVP suporta apenas **análise DC estacionária de baixa tensão** (fontes DC, resistências, interruptores, lâmpadas resistivas, terra), com solver MNA próprio. AC, transitórios, semicondutores e instalações 230/400 V ficam para a Fase 2.

## Consequências

- O solver e o catálogo iniciais ficam pequenos e testáveis com resultados analíticos.
- Componentes sem modelo devem ser assinalados como `não suportado pelo solver` em vez de produzir resultados inventados.
- Os resultados são educativos e aproximados; a interface deve indicá-lo.
- A evolução para ngspice (Fase 2) não deve exigir alterar o modelo canónico JSON.
