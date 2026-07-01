# 08 — Logging, Observabilidade e Administração de Logs

> Consolida decisões tomadas em conversa de arquitetura (2026-07-01):
> convenção de nome de logger (adendo skill 00), separação de camadas
> reforçada com enforcement técnico (skill 05 §2.6), formato de console,
> nova pasta `logs/` de escopo Core (adendo skill 01), parâmetros de
> nível em `system_config` (adendo skill 03), e tela administrativa de
> consulta/exclusão de logs (Core, RBAC padrão, sem tier separado —
> skill 00, Adendo Fase 7a). Convenção de status usada: [DECIDIDO] /
> [ABERTO] / [PENDENTE-SKILL] (mesma convenção da skill 05).

---

## 0. Escopo

Aplica-se a Core, Addons, Features e Plugins do Tesseract. O
`tesseract-device-bridge` (repositório separado) replica a mesma
convenção de nomenclatura/formato em documento próprio dentro do seu
repositório — ver seção 7 — não é coberto diretamente por esta skill.

---

## 1. Convenção de nome de logger [DECIDIDO] (adendo à skill 00)

Nome de logger segue o mesmo padrão de namespace por ponto já usado
para evento no EventBus (skill 00, tabela de convenção de casing):

| Escopo | Padrão de nome | Exemplo |
|---|---|---|
| Core | `core.[subsistema]` | `core.module_manager`, `core.event_bus` |
| Addon (núcleo) | `[addon_name]` | `device_manager`, `brewstation` |
| Feature | `[addon_name].[feature_name]` | `brewstation.mash_control` |
| Serviço específico dentro de um módulo | `[addon_name].[servico]` | `device_manager.mqtt` |

Nomes completos (não sigla de tabela) — legibilidade em log importa mais
que brevidade, ao contrário do prefixo de tabela (skill 02, que usa
sigla por causa do limite de 63 bytes do Postgres — restrição que não
existe em nome de logger).

**Proibido**: `logging.getLogger(__name__)` cru — gera caminho de
arquivo Python no lugar de um nome legível. Todo módulo obtém seu
logger via um helper central do Core (nome e assinatura exatos ficam
para a fase de implementação, não fazem parte desta skill).

---

## 2. Modelo de camadas [DECIDIDO] (reforço da skill 05 §2.6, com enforcement técnico novo)

A skill 05 §2.6 já havia decidido o modelo de 3 camadas para o
`device_manager`; esta skill generaliza para qualquer Addon e formaliza
o mecanismo técnico que faltava:

| Camada | Destino | Enforcement |
|---|---|---|
| Estado atual / cache | Banco (`tesseract_*`) | — (já coberto pela skill 02) |
| Log de rotina (integração, alto volume) | Arquivo local do Addon (`logs/`, já coberto pela skill 03, campo `logging`) | Logger do Addon configurado com `propagate=False` — **nunca** sobe para o log global/console |
| Erro grave (broker inacessível, payload inválido, falha de fail-safe) | Log global do Core | Logger separado (`core.[addon_name]` ou equivalente), que **não** tem `propagate=False` |

**Causa-raiz do sintoma relatado** ("tudo misturado no console"): sem o
`propagate=False` acima, todo log de rotina de qualquer Addon sobe para
o root logger e aparece no console junto com erro grave — o modelo de 3
camadas já existia na skill 05, mas não era **imposto** tecnicamente.

---

## 3. Formato de saída do console [DECIDIDO]

```
HH:MM:SS | LEVEL | logger.name | mensagem
```

- Cor por nível (`DEBUG`/`INFO`/`WARNING`/`ERROR`) — **somente** no
  handler de console, nunca no arquivo (arquivo precisa ser grep-ável
  sem código ANSI).
- Nome do logger com padding fixo para alinhamento visual.
- Console mostra, por padrão: tudo do Core + qualquer coisa que suba
  para a camada de erro grave de qualquer Addon. Log de rotina (camada
  2) não aparece no console por padrão — só no arquivo local do Addon
  responsável.

---

## 4. Estrutura de pastas [PENDENTE-SKILL → aplicado aqui] (adendo à skill 01)

Skill 01 hoje só define `logs/` como pasta **opcional por Addon**
(atrelada a `addon.json.logging`). Não existe pasta de log do **Core**.

**Adendo**: nova pasta `logs/` na **raiz do projeto** (irmã de `core/`,
`addons/`, `plugins/`), para o log global do Core (camada 3, seção 2
acima):

```
tesseract/
├── core/
├── addons/
├── plugins/
├── logs/                      ← NOVO — log global do Core
│   └── core.log
└── ...
```

Mesmo padrão de rotação (`RotatingFileHandler`) já usado pelos Addons
(skill 03, campo `logging`) — tamanho/backup count com os mesmos
defaults (`5 MiB` / `5` backups), configuráveis via `system_config`
(seção 5 abaixo), não hardcoded.

---

## 5. Parâmetros de runtime [DECIDIDO] (adendo à skill 03, `system_config`)

Novo namespace `logging.*`, seguindo a convenção `[namespace].[parametro]`
já estabelecida:

| Chave | Tipo | Default | Efeito |
|---|---|---|---|
| `logging.level.default` | string (`DEBUG`/`INFO`/`WARNING`/`ERROR`) | `INFO` | Nível global de fallback (console + arquivo global) |
| `logging.level.<logger_name>` | string | herda do default | Override por módulo/logger específico, ex.: `logging.level.device_manager.mqtt = WARNING` |
| `logging.global_log_max_bytes` | int | `5242880` (5 MiB) | Rotação do `logs/core.log` |
| `logging.global_log_backup_count` | int | `5` | Backups mantidos do log global |

---

## 6. Administração de Logs — tela nova [DECIDIDO]

Infraestrutura de Core, mesma categoria de `Transação`/`CodeSnapshot`
(skill 00, Adendo Fase 7a) — **não passa pelo CrudGen**, não tem model
tradicional de banco.

### 6.1 Armazenamento e escopo [DECIDIDO]

- Fonte dos dados: **arquivo puro** — a tela lê e apaga direto do
  disco, sem tabela nova no banco.
- Escopo listado: log global do Core (`logs/core.log`, seção 4) **+**
  log local de cada Addon que declarar `addon.json.logging` (skill 03).
- `ModuleManager` é a fonte de verdade de quais Addons têm log local
  ativo — a tela não hardcoda a lista, consulta os manifestos
  carregados em runtime.

### 6.2 Permissões RBAC [DECIDIDO]

Segue a convenção `<plural>.<acao>` da skill 00 — **sem tier/flag de
admin separado**, mesma decisão já registrada no Adendo Fase 7a
("nenhum sistema de tier separado"):

| Permissão | Efeito | Atribuição típica |
|---|---|---|
| `logs.view` | Consultar/visualizar conteúdo dos arquivos de log | Qualquer Role que o admin decidir conceder |
| `logs.delete` | Apagar (deletar) arquivo de log | Na prática, só a Role Admin recebe — por atribuição de RBAC, não por código especial |

### 6.3 Semântica de exclusão [DECIDIDO, com nota técnica em aberto]

**Decidido**: apagar = deletar o arquivo (`unlink`), não truncar. O
handler de log recria o arquivo na próxima escrita.

**[ABERTO — nota técnica, não bloqueia a skill, mas precisa ser
resolvido na Fase de implementação]**: `RotatingFileHandler` padrão do
Python mantém o file descriptor aberto; se o arquivo for deletado
enquanto o handler está com ele aberto, em sistemas POSIX a escrita
continua indo para o inode antigo (já removido do diretório) até o
handler ser fechado/reaberto — o arquivo "novo" só aparece no próximo
`doRollover()` (rotação) ou reinício do processo, não necessariamente
"na próxima escrita" como o nome sugere. Se esse comportamento não for
aceitável na prática, a alternativa é usar
`logging.handlers.WatchedFileHandler` (detecta arquivo removido/trocado
e reabre automaticamente) no lugar do `RotatingFileHandler` para os
logs que passam por esta tela admin. Decisão de qual handler usar fica
para a Fase de implementação — registrado aqui para não ser esquecido.

### 6.4 Estrutura de arquivo/controller/template [DECIDIDO] (aplica skill 01)

Entidade (plural, para nomenclatura): `logs`.

| Arquivo | Local | Papel |
|---|---|---|
| `controller/core/logs.py` | Core | Rotas web da tela admin (listar, visualizar, apagar) |
| `templates/core/logs/manage.html` | Core | Listagem dos arquivos de log (Core + por Addon), com nível/tamanho/data de modificação |
| `templates/core/logs/detail.html` | Core | Visualização do conteúdo de um arquivo (provavelmente paginado/tail — detalhe de UX fica para implementação) |

Sem `_hooks.py` — não é gerado por CrudGen, é código Core escrito à mão,
mesma categoria de `auth`/`dashboard` (skill 01, `controller/core/`).

---

## 7. Tesseract Device Bridge — convenção espelho [DECIDIDO]

O Device Bridge (repositório separado, sem `addon.json`/`system_config`/
CrudGen) **não** ganha uma skill Tesseract própria — ganha um documento
equivalente dentro do seu próprio repositório (ex.: `docs/logging.md`),
que:

- Referencia esta skill (08) como origem da convenção;
- Adapta o namespace de logger ao vocabulário do bridge: `bridge.gpio`,
  `bridge.mqtt`, `bridge.recipe_engine`, `bridge.frontend_api`;
- Adapta o controle de nível (que aqui é via `system_config`) para
  variável de ambiente, já que o bridge não tem banco de config em
  runtime: `LOG_LEVEL`, `LOG_LEVEL_<MODULO>`.

Formato de console (seção 3) e modelo de camadas (seção 2, adaptado —
o bridge não tem "Addon", mas pode replicar rotina-vs-erro-grave por
módulo) são idênticos entre os dois repositórios.

---

## 8. Checklist de validação [DECIDIDO] (adendo ao checklist da skill 03)

- [ ] Nenhum logger é obtido via `logging.getLogger(__name__)` cru —
      sempre pelo helper central com nome no formato da seção 1
- [ ] Todo Addon com `addon.json.logging` presente tem
      `propagate=False` configurado no logger de rotina
- [ ] Log de erro grave de um Addon não usa o mesmo logger do log de
      rotina (loggers distintos, um propaga, outro não)
- [ ] `logs/` na raiz do projeto existe e está no `.gitignore` (log não
      é versionado — só a estrutura/rotação é)
- [ ] Permissões `logs.view`/`logs.delete` seedadas no catálogo RBAC,
      mesmo padrão "código lidera, banco segue" do catálogo de
      Transações (skill 00, Adendo Fase 7a)
- [ ] Tela admin nunca lista/apaga arquivo fora de `logs/` (Core) ou
      `addons/addon_[nome]/logs/` — nunca caminho arbitrário do disco

---

## 9. Plano de execução (alto nível, sem detalhe de código)

1. Helper central de logger (seção 1) + reforço de `propagate=False`
   nos Addons que já têm `logging` no manifesto (`device_manager` hoje)
2. Handler de console com formato/cor (seção 3) + pasta `logs/` na raiz
   com handler global do Core (seção 4)
3. Parâmetros `logging.*` em `system_config` (seção 5), lidos no boot
4. Permissões `logs.view`/`logs.delete` no catálogo RBAC (seção 6.2)
5. Tela admin (`controller/core/logs.py` + templates, seção 6.4) —
   decidir handler (`RotatingFileHandler` vs `WatchedFileHandler`,
   seção 6.3) antes desta fase
6. Documento espelho no `tesseract-device-bridge` (seção 7)
