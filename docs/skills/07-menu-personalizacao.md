# 07 — Personalização de Menu (Ordem e Colapso)

> **Status: SKILL FORMALIZADA (fase de decisão, 2026-07-01).** Nasceu
> de um bug reportado ("o menu deve carregar com os itens colapsados,
> encolhidos, e ter forma de ordenar o menu"), que expôs uma lacuna
> real: nenhuma das skills 00–04 define onde vive o estado de
> ordem/colapso de menu. Mesmo peso normativo das demais skills.
>
> Convenção de status (igual skill 05/06): **[DECIDIDO]** /
> **[ABERTO]** / **[PENDENTE-SKILL]**.

---

## 0. Decisão raiz

**[DECIDIDO]** Dois estados independentes, cada um com dois níveis de
customização (padrão global definido pelo admin, com override opcional
por usuário):

| Estado | O que controla |
|---|---|
| Ordem dos **grupos** de menu | Em que ordem os blocos de Core/Addon/Feature/Plugin aparecem na sidebar |
| Grupos **colapsados por padrão** | Se um grupo específico começa fechado ou aberto ao carregar a tela |
| Sidebar **inteira** aberta/fechada | Modo compacto vs. expandido da sidebar como um todo — estado independente dos dois acima |

**[DECIDIDO]** Escopo da v1: reordenação é **só de grupos** (Addon/
Feature/Plugin/Core inteiros), não dos itens individuais dentro de um
grupo — esses continuam seguindo a ordem declarada pelo próprio módulo
(`menu_config.json`, skill 01). Reordenação granular por item fica
registrada aqui como extensão futura, não coberta por esta versão da
skill.

---

## 1. Onde cada nível vive

| Nível | Papel | Onde |
|---|---|---|
| Autoria (valor de fábrica, por módulo) | Ordem relativa sugerida, label, ícone — definido por quem escreveu o Addon/Feature/Plugin | `menu_config.json` na raiz do módulo (skill 01, adenda desta skill) |
| Padrão global (admin, runtime) | Override do valor de fábrica, aplicado a todo usuário que não tiver override próprio | `system_config` (skill 03, seção 5) |
| Override individual (usuário, runtime) | Sobrepõe o padrão global só para aquele usuário | `tesseract_user_menu_preference` (tabela nova, seção 2) |

Resolução em runtime, nesta ordem de prioridade: override do usuário
→ padrão global (`system_config`) → valor de autoria (`menu_config.json`).
Qualquer nível ausente cai para o próximo.

---

## 2. Schema de dados

### 2.1 Chaves em `system_config` (skill 03, convenção `[namespace].[parametro]`)

| Chave | Tipo | Conteúdo |
|---|---|---|
| `core.menu.group_order` | JSON | Lista ordenada de identificadores de grupo (`core`, `addon_[nome]`, `plugin_[nome]`) |
| `core.menu.default_collapsed_groups` | JSON | Lista de identificadores de grupo que começam colapsados |
| `core.menu.default_sidebar_collapsed` | Boolean | Estado padrão da sidebar inteira |

### 2.2 `tesseract_user_menu_preference` (Core, prefixo fixo — skill 02)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | Integer, PK | |
| `user_id` | Integer, FK → `tesseract_user.id` | Sempre permitido (skill 02) |
| `group_order_json` | JSON, nullable | `null` = herda o padrão global |
| `collapsed_groups_json` | JSON, nullable | `null` = herda o padrão global |
| `sidebar_collapsed` | Boolean, nullable | `null` = herda o padrão global |
| `updated_at` | DateTime | |

---

## 3. Adenda à skill 01

**[PENDENTE-SKILL → skill 01, já aplicada]** `menu_config.json` passa
a existir também na raiz de Addon e de Plugin (antes só existia por
Feature). Ver skill 01, seção "Estrutura obrigatória de um Addon"/
"...de um Plugin", nota adicionada. Papel do arquivo: só o valor de
**autoria** (seção 1 desta skill) — nunca o override de runtime.

---

## 4. RBAC

| Permissão | Escopo |
|---|---|
| `system_config.menu_settings` | Editar o **padrão global** (`core.menu.*`) |
| — (nenhuma permissão nova) | Editar a **própria** preferência não exige permissão além de estar autenticado — o escopo já é restrito ao próprio `user_id` por design |

---

## 5. Pendências desta skill

- [ABERTO] Nenhuma pendência de arquitetura identificada até aqui.
  Pendências de implementação (ex.: biblioteca de drag-and-drop para
  reordenar grupos na UI) ficam para quando a fase de código desta
  skill for autorizada.
