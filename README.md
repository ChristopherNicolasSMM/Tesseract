<p align="center">
  <img src="docs/imgs/logo.png" alt="Tesseract" width="100%">
</p>

<p align="center"><strong>Tesseract By Christopher N. S. M. Mauricio .'.</strong></p>


# Tesseract

O projeto que une tudo... Agora temos um Hub modular (Core + Addons + Features + Plugins) em Flask.
A fusão arquitetural de três projetos anteriores: 
- **PyTeca** (CrudGen, RBAC, versionamento)
- **BrewStation** (motor de descoberta/registro de módulos) 
- **DEVStationFlask** (transações, motor de regras, Designer drag-and-drop, OData com Lib S2MOdataPy)

*Uso inicial: gestão de cervejaria caseira.*
*Uso de longo prazo: base reaproveitável para outros sistemas.*


#### Atualizações da versão vigente:

> **Versão:** 0.0.1

> **Status atual: Validado de ponta a ponta — Core completo +
> Migrations.** Login, navegação, CRUD com clique real (criar/editar/
> lixeira/restaurar/excluir), Roles/Permissions, Versionamento
> (histórico/diff/restauração), tema claro/escuro por usuário, perfil,
> e filtro/paginação nas listas (smart-list-lite). `Flask-Migrate`
> integrado — `db.create_all()` nunca altera tabela existente, então
> qualquer coluna nova exige `python run.py db migrate && db upgrade`
> a partir de agora. Próximo: Fase 7b (motor de regras) ou Fase 7c
> (Designer visual).

---

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

# Migrations — sempre que ALTERAR coluna de um model que JÁ tinha
# tabela criada (db.create_all() nunca faz ALTER, só CREATE de tabela
# nova). Addon/Feature/model novo não precisa disso.
python run.py db migrate -m "descrição da mudança"
python run.py db upgrade

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
| 5 + 5b | `addon_brewstation`/`feature_yeast_bank` completo (8 tabelas) | ✅ |
| 6 | Demais Features Brew (`mash_control`, `device_manager` — CRUD; `integ_bfather` fora) | ✅ |
| 7a | Catálogo de Transações | ✅ |
| 7b/7c | Motor de regras / Designer visual | ⏳ próxima |
| 8 | OData / Screen Generator (DEVStationFlask) | |

## Assets estáticos (Nice Admin)

Já presentes em `static/` (Bootstrap, ApexCharts, Boxicons, Quill,
TinyMCE, ECharts + CSS próprios do PyTeca) — subidos direto no
repositório, fora do fluxo desta conversa.

## Licença / Autor


> **Autor:** Christopher Nicolas Santa Maria Mauricio
> **Projeto:** Tesseract Modular Python Framework

O Tesseract adota um modelo de licenciamento **Source-Available Meritocrático**. 
Acreditamos que o acesso ao código de alto nível deve ser conquistado, seja através de investimento financeiro para acelerar seus negócios, ou de investimento intelectual para fortalecer a comunidade.

### 💼 Opção A: Licenciamento Comercial
Para equipes e indivíduos que desejam utilizar o Tesseract como base para projetos fechados ou comerciais:
*   **Uso Pessoal/Estudos:** $5 USD / trimestral ou $20 USD / vitalício (inclui atualizações).
*   **Uso Comercial/Empresarial:** $100 USD / usuário (vitalício) ou $20 USD / usuário por ano.

### 🛠️ Opção B: Licenciamento Meritocrático (Work-to-Play)
Você pode adquirir licenças de uso vitalícias e gratuitas contribuindo para o desenvolvimento do Tesseract. 
Acumule **5 pontos** através de Pull Requests aprovados para ganhar 1 Licença de Usuário Vitalícia.

**Tabela de Pontuação:**
*   **1 Ponto:** Correções menores (falhas de caractere, documentação, novas legendas/idiomas por addon/plugin/tela).
*   **2 Pontos:** Melhorias de infraestrutura ou segurança básica.
*   **4 Pontos:** Correções de vulnerabilidades críticas que comprometam dados ou arquitetura.
*   **5 Pontos:** Desenvolvimento de novas funcionalidades core, Addons ou Plugins estruturais.

*Empresas são encorajadas a alocar desenvolvedores para o nosso backlog. Ao contribuir com código, a empresa não apenas melhora a ferramenta que utiliza, mas adquire licenças gratuitas para sua equipe.*

Para todos os detalhes legais, restrições de distribuição e termos de uso, consulte o arquivo [`LICENSE`](LICENSE) na raiz deste repositório.

