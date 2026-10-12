# 0004. Backend Python obrigatório no MVP

- **Estado:** Aceite
- **Data:** 2026-10-12

## Contexto

A geração automática, a validação topológica e o solver MNA beneficiam do ecossistema Python (Pydantic, NumPy/SciPy, Schemdraw). O GitHub Pages só serve conteúdo estático. A simulação totalmente no browser (solver em TypeScript ou Pyodide) é possível mas aumenta o âmbito.

## Decisão

O MVP exige um **backend Python (FastAPI)** para geração, validação e simulação, alojado em Debian com Docker e HTTPS. O frontend é estático (GitHub Pages). A simulação no browser fica como evolução opcional.

## Consequências

- O editor funciona offline para desenhar e guardar (IndexedDB), mas validar/simular/gerar requer a API.
- A API deve aplicar CORS restrito, limites de payload, timeouts e rate limiting.
- Nunca executar código Python enviado pelo cliente; a geração usa apenas templates e parâmetros validados.
- O backend fica fora do workspace pnpm, com dependências em `requirements.txt`.
