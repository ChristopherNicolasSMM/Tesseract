# 01 — Visão Geral (Sistema)

## Propósito

Tesseract é o Hub modular (Core + Addons + Features + Plugins) que
unifica três projetos anteriores em uma única base:

- **PyTeca** — CrudGen (geração de CRUD a partir de model anotado),
  RBAC, versionamento de código gerado.
- **BrewStation** — motor de descoberta e registro de módulos
  (resolução de prefixo de tabela, multi-pass de FK — substituído
  por uma abordagem mais simples, ver Fase 1 no `BACKLOG.md`).
- **DEVStationFlask** — transações, motor de regras, Designer
  drag-and-drop, OData (ainda não portados — Fases 7/8).

Uso inicial: gestão de cervejaria caseira (`addon_brewstation`). Uso de
longo prazo: base reaproveitável para outros domínios.

## Estado atual (ver `BACKLOG.md` para o detalhe fase a fase)

| Camada | Status |
|---|---|
| Core (`ModuleManager`, `EventBus`, DB factory, logging) | Pronto (Fase 1) |
| RBAC + Usuários | Pronto (Fase 2) |
| Versionamento (`CodeSnapshot`) | Pronto, mas só usado pelo CrudGen (Fase 3/4) |
| CrudGen + Anotações | Pronto (Fase 4) |
| Primeiro Addon real (`addon_brewstation`/`feature_yeast_bank`) | Parcial — só `YeastStrain` (Fase 5) |
| Designer/OData (herdados do DEVStationFlask) | Não iniciado |

## Dependências do Core

`Flask`, `Flask-SQLAlchemy`, `Flask-Login`, `Jinja2` (via Flask),
`psycopg2-binary` (só usado em produção/Postgres). Ver
`requirements.txt`.

## O que o Core expõe (`provides`)

- `core.module_manager.ModuleManager` — ciclo de descoberta/registro
  de Addons, aplicação de prefixo de tabela, sincronização de
  permissão (ver "O que isso muda" abaixo).
- `core.event_bus.event_bus` — pub/sub síncrono em memória.
- `core.permissions.permission_required` — decorator de autorização.
- `core.crudgen.generator.generate()` — geração de CRUD a partir de
  model anotado.
- `core.versioning.snapshot_if_needed()` — versionamento de arquivo
  gerado/editado.

## O que mudou desde o desenho original (skill 02)

A skill 02 previa o prefixo de tabela sendo aplicado "no momento do
registro" — na prática, só ficou assim a partir da Fase 5, quando o
primeiro Addon real expôs que aplicar só no `generate` (Fase 4) não
sobrevive a um reboot normal do app. Ver `BACKLOG.md`, seção "3 bugs
reais encontrados só ao migrar o primeiro Addon de verdade".

## Documentos relacionados

- [02-diagrama-c4.md](02-diagrama-c4.md)
- [03-fluxos.md](03-fluxos.md)
- [04-modelo-de-dados.md](04-modelo-de-dados.md)
- [05-casos-de-uso.md](05-casos-de-uso.md)
- [06-manutencao-e-expansao.md](06-manutencao-e-expansao.md)
