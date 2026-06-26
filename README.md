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

> **Status atual: Fases 7 (a/b/c) e 8 concluídas.** Motor de regras
> (Validação conectada de verdade), Designer visual drag-and-drop
> (canvas real, sem framework de frontend), e integração OData
> (ConnectionManager + navegador de dados read-only). O Designer
> fechou o ciclo da Fase 7b: regras de Validação anexadas a um
> componente aparecem renderizadas e validadas na tela de execução.
> Próximo: Visibilidade/Cálculo no motor de regras (catalogados desde
> a Fase 7b, ainda sem função JS correspondente), ou
> `screen_generator.py` (geração de página a partir de metadata OData,
> agora possível com o Designer existindo).

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

- [01 — Visão Geral](docs/technical/01-visao-geral.md)
- [02 — Diagrama C4](docs/technical/02-diagrama-c4.md)
- [03 — Fluxos](docs/technical/03-fluxos.md)
- [04 — Modelo de Dados](docs/technical/04-modelo-de-dados.md)
- [05 — Casos de Uso](docs/technical/05-casos-de-uso.md)
- [06 — Manutenção e Expansão](docs/technical/06-manutencao-e-expansao.md)
- [07 — Catálogo de Transações](docs/technical/07-catalogo-de-transacoes.md) *(gerado por `python run.py transactions-doc`)*

### Manual do usuário final (sistema)

- [01 — Introdução](docs/manual/01-introducao.md)
- [02 — Primeiros Passos](docs/manual/02-primeiros-passos.md)
- [03 — Funcionalidades](docs/manual/03-funcionalidades.md)
- [04 — Perguntas Frequentes](docs/manual/04-perguntas-frequentes.md)

### Documentação por Addon / Feature

- **`addon_brewstation`** — [técnica](addons/addon_brewstation/docs/technical/01-visao-geral.md) · [manual](addons/addon_brewstation/docs/manual/01-introducao.md)
  - **`feature_yeast_bank`** (8 entidades) — [técnica](addons/addon_brewstation/features/feature_yeast_bank/docs/technical/01-visao-geral.md) · [modelo de dados](addons/addon_brewstation/features/feature_yeast_bank/docs/technical/04-modelo-de-dados.md) · [manual](addons/addon_brewstation/features/feature_yeast_bank/docs/manual/01-introducao.md)
  - **`feature_device_manager`** (4 entidades) — [técnica](addons/addon_brewstation/features/feature_device_manager/docs/technical/01-visao-geral.md) · [modelo de dados](addons/addon_brewstation/features/feature_device_manager/docs/technical/04-modelo-de-dados.md) · [manual](addons/addon_brewstation/features/feature_device_manager/docs/manual/01-introducao.md)
  - **`feature_mash_control`** (12 entidades) — [técnica](addons/addon_brewstation/features/feature_mash_control/docs/technical/01-visao-geral.md) · [modelo de dados](addons/addon_brewstation/features/feature_mash_control/docs/technical/04-modelo-de-dados.md) · [manual](addons/addon_brewstation/features/feature_mash_control/docs/manual/01-introducao.md)

### Migrations

- [`migrations/`](migrations/) — Flask-Migrate/Alembic. Baseline já
  stampada; toda alteração de coluna em tabela existente precisa de
  `python run.py db migrate && db upgrade` (ver
  [docs/technical/06-manutencao-e-expansao.md](docs/technical/06-manutencao-e-expansao.md))

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
| 7b | Motor de regras (Validação conectada) | ✅ |
| 7c | Designer visual drag-and-drop | ✅ |
| 8 | OData (ConnectionManager + navegador read-only; Screen Generator depende da Fase 7c) | ✅ |
| 9 | Promoção `feature_device_manager` → `addon_device_manager` + base p/ MQTT | 🔶 em andamento |

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

