# 0005. Repositório público open source com licença MIT

- **Estado:** Aceite
- **Data:** 2026-10-12

## Contexto

O projeto é um repositório público open source. É preciso escolher uma licença e garantir que as licenças das dependências, componentes e motores de simulação são compatíveis.

## Decisão

Licenciar o código sob a **licença MIT** (ficheiro `LICENSE` na raiz).

- Permissiva e amplamente compreendida, facilita reutilização educativa e contribuições.
- Compatível com as dependências atuais: no frontend/tooling predominam MIT, ISC, BSD e Apache-2.0 (com algumas MPL-2.0 de ferramentas de build); no backend FastAPI e Pydantic (MIT), Uvicorn e Starlette (BSD-3-Clause).

## Consequências

- Novas dependências devem ter licença compatível com distribuição MIT; licenças copyleft fortes (GPL/AGPL) não devem ser incorporadas no código distribuído sem nova decisão.
- O ngspice (Fase 2) deve ser invocado como processo externo, e a sua licença confirmada antes de ser incluído em imagens Docker.
- Rever licenças com `pnpm licenses list -r` e `pip show` antes de cada release.
