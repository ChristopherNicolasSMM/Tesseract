# 08 — Logging, Observabilidade e Administração de Logs

> **Status: EXECUTADO (2026-07-01), com revisões em relação à proposta
> original.** Duas decisões da versão inicial foram revertidas ao
> confrontar a skill com o código real antes de codificar (seções 1 e
> 6.2 — ver histórico riscado em cada uma). Convenção de status usada:
> [DECIDIDO] / [EXECUTADO] / [ABERTO] / [REVISADO] (mesma convenção da
> skill 05).

---

## 0. Escopo

Aplica-se a Core, Addons, Features e Plugins do Tesseract. O
`tesseract-device-bridge` (repositório separado) replica a mesma
convenção de nomenclatura/formato em documento próprio dentro do seu
repositório — ver seção 7 — não é coberto diretamente por esta skill.

---

## 1. Convenção de nome de logger [REVISADO — execução, 2026-07-01]

**Decisão original (abaixo, riscada) foi descartada ao confrontar a
skill com o código real.** `core/logging_config.py` já documentava,
antes desta skill existir, a regra "todo módulo usa
`logging.getLogger(__name__)`" — em uso em ~40 arquivos (Core inteiro,
`addon_brewstation` com 2 Features, `addon_device_manager`). Migrar
pra nomenclatura curta exigiria tocar todos esses arquivos sem ganho
real: o nome de origem **já aparece** no console via `%(name)s`, só
que como caminho de módulo Python (`addons.addon_brewstation.features.
feature_mash_control.services.automation_engine`) em vez de um nome
curto.

**[DECIDIDO] Mantido**: `logging.getLogger(__name__)` continua sendo a
regra real e válida — nenhuma migração de nome de logger. As duas
exceções que já existiam antes desta skill (`mqtt_client_service.py`
usando `"addon_device_manager.mqtt"`, `integration_logger.py` usando
`"addon_device_manager.integration"`) também foram mantidas como estão
— decisão explícita de não renomear pra bater com o nome do manifesto
(`device_manager`), pra não gerar diff sem ganho prático.

<details>
<summary>Decisão original (descartada) — mantida como histórico</summary>

Nome de logger seguiria o mesmo padrão de namespace por ponto já usado
para evento no EventBus (skill 00, tabela de convenção de casing):
`core.[subsistema]` (Core), `[addon_name]` (Addon), `[addon_name].
[feature_name]` (Feature), `[addon_name].[servico]` (serviço
específico). `logging.getLogger(__name__)` cru seria proibido — ideia
descartada, ver decisão revisada acima.
</details>

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

**Causa-raiz do sintoma relatado ("tudo misturado no console") —
revisada, 2026-07-01, após inspeção do código real**: a hipótese
original acima (vazamento por falta de `propagate=False`) **não se
confirmou** — `integration_logger.py` já tinha `propagate=False`
implementado corretamente desde a skill 05, e o log de rotina do MQTT
já não vazava. As causas reais eram outras:
1. `core/logging_config.py` nunca teve handler de arquivo — só um
   `StreamHandler` pro console. Não existia "camada 3 separada", só o
   único destino que existe;
2. `core/module_manager.py`/`core/event_bus.py` logam cada passo em
   `DEBUG` **de propósito**, pra rastreabilidade — em dev
   (`LOG_LEVEL=DEBUG`, default do ambiente), isso sozinho já enche o
   console, por design, não por bug;
3. O formatter já incluía `%(name)s` (nome do logger aparecia), mas
   como caminho de módulo Python completo — verboso, difícil de
   escanear visualmente, mesmo que tecnicamente presente.

Fix real: cor + separação visual por nível (seção 3) + arquivo global
persistido de fato (seção 4) — não uma mudança de propagação, que já
estava correta.

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

### 6.2 Permissões RBAC [REVISADO — execução, 2026-07-01]

**Decisão original (`logs.view`/`logs.delete`, riscada abaixo) foi
descartada.** Ao levantar o código real, as 8 telas admin do Core já
existentes (Users, Roles, Versioning, Field Rules, OData, Designer,
Transactions, Tasks) usam **todas**, sem exceção, uma única permissão
flat `"admin"` (`@permission_required("admin")`) — tanto pra
visualizar quanto pra mutar. Nenhuma delas separa `view` de
`delete`/`edit`. Manter a divisão só na tela de Logs seria a primeira
exceção a esse padrão universal, sem ganho que justifique a
inconsistência.

**[DECIDIDO]**: tela de Logs usa `@permission_required("admin")` em
todas as rotas (listar, ver conteúdo, apagar) — igual às demais 8
telas Core, sem divisão granular.

<details>
<summary>Decisão original (descartada) — mantida como histórico</summary>

Duas permissões seguindo `<plural>.<acao>` (skill 00): `logs.view`
(delegável a qualquer Role) e `logs.delete` (só Role Admin) — descartada
por quebrar a consistência com as demais telas Core, ver decisão acima.
</details>

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

### 6.4 Estrutura de arquivo/controller/template [EXECUTADO — nomes ajustados]

Entidade (plural, para nomenclatura): `logs`. Nomes de arquivo
ajustados na execução pra seguir o padrão real já usado pelas outras 7
telas admin do Core (`admin_users.py`, `admin_versioning.py`,
`admin_odata.py`, etc. — prefixo `admin_`, não previsto na tabela
original desta skill):

| Arquivo | Local | Papel |
|---|---|---|
| `controller/core/admin_logs.py` | Core | Blueprint `admin_logs_bp` — rotas `manage`/`view`/`delete` |
| `core/log_admin_service.py` | Core | `LogAdminService` — listar fontes, ler conteúdo, apagar (mesmo padrão de `core/snapshot_service.py`) |
| `templates/core/admin/logs_manage.html` | Core | Listagem das fontes (Core + por Addon), tamanho/status |
| `templates/core/admin/logs_detail.html` | Core | Conteúdo de um arquivo (últimas 1000 linhas, sem paginação nesta versão) |

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

## 8. Checklist de validação [EXECUTADO] (adendo ao checklist da skill 03)

- [x] ~~Nenhum logger é obtido via `logging.getLogger(__name__)` cru~~
      — item removido, decisão revertida (seção 1): `getLogger(__name__)`
      é a regra real e continua sendo usada
- [x] `addon_device_manager` (único Addon com `logging` no manifesto
      hoje) já tinha `propagate=False` no logger de rotina desde a
      skill 05 — confirmado, nenhuma mudança necessária
- [x] `logs/` na raiz do projeto existe (criada em runtime por
      `configure_logging()`) e está no `.gitignore`
- [x] Permissão `"admin"` (flat, não `logs.view`/`logs.delete` —
      decisão revertida, seção 6.2) usada em todas as rotas de
      `admin_logs.py`, igual às demais telas Core
- [x] Tela admin (`LogAdminService`) só reconhece o log global do Core
      e os logs de Addon descobertos via `module_manager.active_modules`
      — nunca um caminho arbitrário do disco
- [ ] Handler de arquivo global desligado em `TESTING` (mesmo padrão
      do MQTT/scheduler) — decisão nova durante a execução, não estava
      no checklist original; documentado na seção 10

---

## 9. Plano de execução — progresso real

1. **[EXECUTADO]** ~~Helper central de logger~~ — não criado, decisão
   revertida (seção 1): `getLogger(__name__)` mantido, nenhum reforço
   de `propagate=False` necessário (`device_manager` já estava correto)
2. **[EXECUTADO]** Handler de console com formato/cor (seção 3) +
   pasta `logs/` na raiz com handler global do Core (seção 4) —
   `core/logging_config.py`
3. **[EXECUTADO — parcial]** Parâmetros `logging.level.*` em
   `system_config`, lidos via `apply_logging_level_overrides()` depois
   do boot (não em `configure_logging()`, que roda antes de
   `init_db()`). `logging.global_log_max_bytes`/`backup_count` **não**
   ficaram dinâmicos nesta fase — o handler de arquivo precisa existir
   antes do banco estar pronto; permanecem hardcoded com os mesmos
   valores default documentados na seção 5. Nenhuma das duas chaves é
   seedada por padrão (evita que um `logging.level.default` esquecido
   derrube o `DEBUG` verboso de dev)
4. **[EXECUTADO — revisado]** Permissão `"admin"` flat no catálogo RBAC
   (seção 6.2), não `logs.view`/`logs.delete`
5. **[EXECUTADO]** Tela admin (`controller/core/admin_logs.py` +
   `core/log_admin_service.py` + templates, seção 6.4) — semântica de
   exclusão implementada como decidido (`unlink`, não truncar; nota
   técnica do `RotatingFileHandler` da seção 6.3 permanece **[ABERTO]**,
   não bloqueou a execução, comportamento aceito como está)
6. **[ABERTO]** Documento espelho no `tesseract-device-bridge` (seção
   7) — não faz parte deste repositório, fica pendente

---

## 10. Status consolidado (2026-07-01)

**Executado nesta sessão**: seções 1 (revisada), 2 (causa-raiz
revisada), 3, 4, 5 (parcial), 6 completa (6.2 revisada), 8 (checklist
atualizado). 283/283 testes passando (13 novos, cobrindo formatter,
`LogAdminService` e permissão da tela admin).

**Decisão nova, fora do escopo original desta skill**: handler de
arquivo global desligado quando `app.config["TESTING"]` é verdadeiro —
mesmo padrão já usado pelo cliente MQTT e pelo scheduler de tasks
("nunca em modo de teste"). Evita escrever centenas de linhas em disco
a cada execução da suíte e evita lock de arquivo no Windows entre apps
de teste sucessivos.

**Pendente**: item 6 do plano de execução (documento espelho no
Device Bridge) e a nota técnica aberta da seção 6.3
(`RotatingFileHandler` vs `WatchedFileHandler` no cenário de exclusão
enquanto o processo está rodando).
