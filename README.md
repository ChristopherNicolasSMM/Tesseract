# Tesseract

Hub modular (Core + Addons + Features + Plugins) em Flask — fusão
arquitetural de três projetos anteriores: **PyTeca** (CrudGen, RBAC,
versionamento), **BrewStation** (motor de descoberta/registro de módulos) e
**DEVStationFlask** (transações, motor de regras, Designer drag-and-drop,
OData).

Uso inicial: gestão de cervejaria caseira. Uso de longo prazo: base
reaproveitável para outros sistemas.

> **Status atual: Fase 0 — Scaffold.** Não há Addons/Plugins de domínio
> ainda. O Core sobe e responde em `/health`.

## Navegação

### Padrões e regras (leitura obrigatória antes de codar)

- [`docs/skills/README.md`](docs/skills/README.md) — índice e ordem de leitura
  - [00 — Glossário e Convenções Gerais](docs/skills/00-glossario-e-convencoes-gerais.md)
  - [01 — Nomenclatura de Pastas e Arquivos](docs/skills/01-nomenclatura-pastas-e-arquivos.md)
  - [02 — Nomenclatura de Tabelas e Prefixos](docs/skills/02-nomenclatura-tabelas-e-prefixos.md)
  - [03 — Parâmetros, Argumentos e Manifestos](docs/skills/03-parametros-argumentos-e-manifestos.md)
  - [04 — Padrão de Documentação](docs/skills/04-padrao-de-documentacao.md)

### Documentação técnica (sistema)

- [`docs/technical/01-visao-geral.md`](docs/technical/01-visao-geral.md)
- `docs/technical/02-diagrama-c4.md` *(a criar)*
- `docs/technical/03-fluxos.md` *(a criar)*
- `docs/technical/04-modelo-de-dados.md` *(a criar)*
- `docs/technical/05-casos-de-uso.md` *(a criar)*
- `docs/technical/06-manutencao-e-expansao.md` *(a criar)*

### Manual do usuário final

- [`docs/manual/01-introducao.md`](docs/manual/01-introducao.md)
- `docs/manual/02-primeiros-passos.md` *(a criar)*
- `docs/manual/03-funcionalidades.md` *(a criar)*
- `docs/manual/04-perguntas-frequentes.md` *(a criar)*

### Planejamento

- [`BACKLOG.md`](BACKLOG.md) — backlog vivo, organizado por fase

## Como rodar (Fase 0)

```bash
pip install -r requirements.txt
flask --app wsgi run --debug
# GET /health → confirma que o Core subiu
```

## Fases de construção (resumo — detalhe completo no `BACKLOG.md`)

| Fase | Entregável |
|---|---|
| 0 | Scaffold de pastas, Core mínimo, README navegável |
| 1 | `ModuleManager`, `EventBus`, template loader, DB factory |
| 2 | RBAC + Usuários (portado do PyTeca) |
| 3 | Versionamento (`CodeSnapshot`, portado do PyTeca) |
| 4 | CrudGen + Anotações (portado do PyTeca) |
| 5 | `addon_brewstation` — primeira Feature real (`yeast_bank`) |
| 6 | Demais Features Brew (`mash_control`, `device_manager`, `integ_bfather`) |
| 7 | `addon_builder` — Designer drag-and-drop + motor de regras (DEVStationFlask) |
| 8 | OData / Screen Generator (DEVStationFlask) |

## Assets estáticos (Nice Admin)

A pasta `static/` está vazia de propósito nesta fase — assets de
CSS/JS/fontes do template Nice Admin entram depois, via commit separado.

## Licença / Autor

A definir.
