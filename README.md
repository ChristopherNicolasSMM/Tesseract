# Tesseract

Hub modular (Core + Addons + Features + Plugins) em Flask — fusão
arquitetural de três projetos anteriores: **PyTeca** (CrudGen, RBAC,
versionamento), **BrewStation** (motor de descoberta/registro de módulos) e
**DEVStationFlask** (transações, motor de regras, Designer drag-and-drop,
OData).

Uso inicial: gestão de cervejaria caseira. Uso de longo prazo: base
reaproveitável para outros sistemas.


> **Status atual: Fase 5 — primeiro Addon real.** `addon_brewstation`/
> `feature_yeast_bank` descoberto automaticamente a partir de `addons/`,
> com `YeastStrain` gerado via CrudGen, tabela
> `tesseract_brewstation_yeastbank_strain`, CRUD funcional via HTTP e
> permissões reais. As demais 7 tabelas de `yeast_bank` ficam para a
> Fase 5b — o pipeline Addon+Feature+ModuleManager+CrudGen já está
> provado de ponta a ponta.

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

## Como rodar (Fase 5)

Não é necessário ter o executável `flask` instalado globalmente —
`run.py` expõe todos os comandos via `python run.py ...`.

```bash
pip install -r requirements.txt

# Dev (SQLite, criado em instance/tesseract_dev.db na primeira execução)
python run.py start
python run.py start --port 8000 --debug

# Primeiro usuário admin (toda a API de usuários é admin-only)
python run.py init-admin --username admin --password admin123

# Gerar CRUD a partir de um model anotado (Fase 4 — CrudGen)
python run.py generate --model caminho/para/model.py --addon brewstation [--feature yeast_bank] [--overwrite]

# Outros comandos úteis (built-in do Flask, vêm de graça)
python run.py routes      # lista todas as rotas registradas
python run.py shell       # shell Python com o app já carregado
python run.py --help      # lista todos os comandos disponíveis

# Login (sessão via cookie)
curl -i -c cookies.txt -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Produção (Postgres obrigatório via DATABASE_URL)
export TESSERACT_ENV=production
export DATABASE_URL=postgresql://user:senha@host:5432/tesseract
python run.py start

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
| 4 | CrudGen + Anotações (portado do PyTeca) | ✅ |
| 5 | `addon_brewstation` — primeira Feature real (`yeast_bank`) | ✅ (YeastStrain; demais tabelas em 5b) |
| 6 | Demais Features Brew / resto do yeast_bank | ⏳ próxima |
| 7 | `addon_builder` — Designer drag-and-drop + motor de regras (DEVStationFlask) | |
| 8 | OData / Screen Generator (DEVStationFlask) | |

## Assets estáticos (Nice Admin)

Já presentes em `static/` (Bootstrap, ApexCharts, Boxicons, Quill,
TinyMCE, ECharts + CSS próprios do PyTeca) — subidos direto no
repositório, fora do fluxo desta conversa.

## Licença / Autor

A definir.
