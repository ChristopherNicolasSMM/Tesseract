# Tesseract

Hub modular (Core + Addons + Features + Plugins) em Flask — fusão
arquitetural de três projetos anteriores: **PyTeca** (CrudGen, RBAC,
versionamento), **BrewStation** (motor de descoberta/registro de módulos) e
**DEVStationFlask** (transações, motor de regras, Designer drag-and-drop,
OData).

Uso inicial: gestão de cervejaria caseira. Uso de longo prazo: base
reaproveitável para outros sistemas.

> **Status atual: Fase 3 — Versionamento.** `CodeSnapshot` funcionando
> (com captura automática de edição manual perdida), `system_config`
> com seed idempotente de chaves padrão. Ainda sem CrudGen — entra na
> Fase 4 — e sem nenhum Addon/Plugin de domínio real — entra na Fase 5.

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

## Como rodar (Fase 3)

```bash
pip install -r requirements.txt

# Dev (SQLite, criado em instance/tesseract_dev.db na primeira execução)
flask --app wsgi run --debug

# Primeiro usuário admin (toda a API de usuários é admin-only)
flask --app wsgi init-admin --username admin --password admin123

# Login (sessão via cookie)
curl -i -c cookies.txt -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Produção (Postgres obrigatório via DATABASE_URL)
export TESSERACT_ENV=production
export DATABASE_URL=postgresql://user:senha@host:5432/tesseract
flask --app wsgi run

# Testes (SQLite em memória, isolado)
TESSERACT_ENV=testing python -m pytest tests/ -v
```

## Fases de construção (resumo — detalhe completo no `BACKLOG.md`)

| Fase | Entregável | Status |
|---|---|---|
| 0 | Scaffold de pastas, Core mínimo, README navegável | ✅ |
| 1 | `ModuleManager`, `EventBus`, template loader, DB factory | ✅ |
| 2 | RBAC + Usuários (portado do PyTeca) | ✅ |
| 3 | Versionamento (`CodeSnapshot`, portado do PyTeca) | ✅ |
| 4 | CrudGen + Anotações (portado do PyTeca) | ⏳ próxima |
| 5 | `addon_brewstation` — primeira Feature real (`yeast_bank`) | |
| 6 | Demais Features Brew (`mash_control`, `device_manager`, `integ_bfather`) | |
| 7 | `addon_builder` — Designer drag-and-drop + motor de regras (DEVStationFlask) | |
| 8 | OData / Screen Generator (DEVStationFlask) | |

## Assets estáticos (Nice Admin)

A pasta `static/` está vazia de propósito nesta fase — assets de
CSS/JS/fontes do template Nice Admin entram depois, via commit separado.

## Licença / Autor

A definir.
