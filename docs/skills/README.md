# Skills de Padronização do Tesseract

Conjunto de regras obrigatórias para qualquer construção (manual ou via IA)
dentro do projeto Tesseract — fusão de PyTeca (CrudGen, RBAC, versionamento),
BrewStation (motor de descoberta/registro) e DEVStationFlask (persistência
de estado, transações, regras).

Ordem de leitura recomendada:

1. **00-glossario-e-convencoes-gerais.md** — termos (Core/Addon/Plugin/Feature/
   Module/Transação/Hook/CrudGen/Snapshot), convenções de idioma/casing, i18n.
2. **01-nomenclatura-pastas-e-arquivos.md** — estrutura de diretórios do Core,
   de um Addon e de um Plugin; nomenclatura de arquivos e classes.
3. **02-nomenclatura-tabelas-e-prefixos.md** — regra tri-nível de prefixo de
   tabela, limite de 55 caracteres, regra de PK externa (Integer +
   `external_id`), regra de FK entre módulos (incluindo entre Features do
   mesmo Addon).
4. **03-parametros-argumentos-e-manifestos.md** — schema de `addon.json`,
   `feature.json`, `plugin.json`; argumentos da CLI do CrudGen; parâmetros de
   runtime em `system_config`.
5. **04-padrao-de-documentacao.md** — padrão de documentação técnica
   (C4, fluxos, ER/MER, casos de uso) e manual do usuário final, e onde cada
   um vive em `docs/`.
6. **05-proposta-addon-device-manager-e-mqtt.md** — convenção EventBus vs.
   MQTT, promoção de Feature a Addon independente, schema de dispositivos
   IoT e fail-safe (LWT agregado).
7. **06-model-builder-e-playground.md** — tela web de criação de Model/
   Addon/Feature (equivalente ao CrudGen via CLI, herdado do PyTeca) e
   API/SQL Playground.
8. **07-menu-personalizacao.md** — ordem e colapso de grupos de menu,
   com padrão global (admin) e override por usuário.
9. **08-logging-observabilidade-e-administracao.md** — convenção de nome
   de logger, separação de camadas de log (rotina vs. erro grave) com
   enforcement técnico, formato de console, log global do Core (`logs/`
   na raiz), e tela administrativa de consulta/exclusão de logs (RBAC
   padrão, sem tier separado).
10. **09-auto-descoberta-modulos.md** — descoberta automática de rotas/
    models/menu via `pkgutil.walk_packages`, escopada por Addon/Feature
    (adaptação do mecanismo real do PyTeca à arquitetura tri-nível).
11. **10-menu-hierarquico.md** — menu em árvore de profundidade
    arbitrária (`parent_id`/`order_index` em Transaction), substitui o
    campo `group` plano; adendas nas skills 07 e 09.
12. **11-referencia-fraca-e-display-field.md** — resolução de campo de
    referência fraca (skill 02) em nome legível na tela gerada e em
    combo de busca, via `@display_field`/`@weak_ref` + geração
    automática pelo CrudGen + `/api/options/<table>`.
13. **12-crudgen-referencia-completa.md** — referência completa do
    CrudGen: pipeline model→CLI→arquivos, guia de uso de cada
    anotação (`@label`/`@plural`/`@choices`/`@required`/`@max_length`/
    `@min_length`/`@min_value`/`@display_field`/`@weak_ref`/
    `@menu_icon`/`@permission`), semântica de hooks/`--overwrite`/
    `--only templates`, e a migração de 3 módulos reais pro caminho
    de auto-descoberta (skill 09).
14. **13-crudgen-guia-operacional.md** — companheiro da skill 12:
    fluxo de objetos completo (request→controller→service→model→DB,
    Web e API, com a assimetria real de `manage()` não passar pelo
    `Service.list()`), os únicos 2 pontos reais de hook de lifecycle
    (`pbo_apply_fields`/`pai_apply_fields`, só em create/update — não
    existe em trash/restore/delete_permanent nem em controller/rotas),
    checklist completo de "como adicionar um campo", e cookbook de
    manutenções comuns.
15. **14-eventbus-convencao.md** — convenção de nome de evento e
    contrato de payload do EventBus (`core/event_bus.py`), catálogo
    real dos 2 eventos em uso hoje, e 2 achados de manutenção (nome de
    evento duplicado como string literal em publisher/subscriber;
    docstring desatualizada em `register_example_listener()`).
16. **15-popups-e-dialogos-padrao.md** — padrão de diálogo de
    confirmação e toast/alert (Core), substituindo `confirm()`/
    `alert()` nativos e o `flash()` duplicado por template; primeiro
    uso real do motor de resolução de i18n (adendo da skill 00),
    delegação de evento obrigatória para sobreviver a fragmento AJAX
    (Plant Workspace/Dashboard).
17. **16-designer-acoes-e-dados.md** — Ações do Designer (catálogo em
    duas camadas: código + `DesignerDataAction`, sempre server-side
    quando toca dado), Provedor OData local (`@odata_expose`,
    atalho em processo), Tier 1/2 de componente (16 tipos), e
    substituição de tela do CrudGen no menu (`replace_in_menu`).
    **Atenção**: as seções sobre o construtor visual são histórico — ele
    foi removido na Fase 12; ver o cabeçalho do próprio arquivo.
18. **17-paginas-customizadas-fluxo-de-dados.md** — como uma página
    customizada consome dado: os três caminhos (API REST do CrudGen,
    Ação de Dado, `/api/options/`), contratos, permissão (401 vs 403),
    segurança (SSTI, XSS no dado da API, nota sobre CSRF) e erros
    comuns. Referência viva em `/freestyle/` (Fase 13, controller
    `controller/core/freestyle_model.py`); modelos estáticos em
    `static/modelo_paginas_nice_admin/_modelo-pagina-{basico,completo}.html`
    também existem, decisão de consolidação em aberto (BACKLOG, Fase 13).
19. **18-freestyle-modelos-de-referencia.md** — estrutura e convenção do
    `/freestyle/` (Fase 13): onde controller/template/JS moram, por que
    `templates/` não é servível, convenção de nome `model_X-*.js` vs.
    `freestyle-*.js` compartilhado, e passo a passo pra criar um modelo
    novo.
20. **19-proposta-reestruturacao-yeast-bank-container.md** — nova
    entidade `YeastContainer` entre Dispositivo e Item do banco
    (Dispositivo 1:N Container 1:N Item), remoção de
    `YeastBankItem.storage_device_id` em favor de `container_id`,
    plano de migration em 6 passos sem perda de dado, e navegação em
    drill-down proposta para a futura tela integrada (BACKLOG, Fase
    14). Model, CrudGen e as 6 migrations já implementados; falta só
    a tela integrada de navegação.
21. **20-proposta-crudgen-tipo-sqlalchemy-html.md** — `_FIELD_HTML_VALIDATIONS`
    (skill 12) ganhou `html_type` via introspecção real de
    `db.Date`/`DateTime`/`Time`/`Integer`/`Float`/`Numeric`/`Boolean`/
    `Text`, mantendo `@enum_field`/`@weak_ref` com prioridade. Sem
    `@calendar` nova. **Executada.**
22. **21-tela-integrada-navegacao-unificacao-evento-starter-contagem.md** —
    `YeastBankEvent` vira ponto de entrada único (Starter/Contagem de
    Células criam registro especializado automaticamente e
    redirecionam); `YeastStorageReading` removida;
    `strain_id`/`starter_id` redundantes removidos de
    `bank_event`/`cell_count_history`; hooks de controller
    (`block_create`/`post_create_redirect`) ficaram reais pela
    primeira vez. Schema/fluxo **executados** (BACKLOG Fase 20); a
    tela integrada em si (2 abas + botões) ainda não foi implementada.

## Status

As skills de fundação (nomenclatura, estrutura, parâmetros, documentação)
estão completas e em uso ativo — toda a construção real do Tesseract até
aqui (Core, RBAC, versionamento, CrudGen, `addon_brewstation` com 3
Features/24 entidades, páginas HTML, Roles/Permissions, catálogo de
Transações, Migrations, `addon_device_manager`) seguiu essas regras.

As skills 06, 07, 08 e 09 já foram **executadas** — ver o próprio
arquivo de cada uma para o detalhe do que foi implementado e eventuais
revisões em relação à proposta original (skill 08, seção 10; skill 06,
Patches A/B/C). A skill 10 (menu hierárquico, `parent_id`/`order_index`
em Transaction) também já foi **executada**. A skill 16 (Designer:
Ações/Dados/Substituição, Fase 10) também já foi **executada** — ao
contrário das demais, nasceu depois da implementação (documento
descritivo, não proposta prévia).

Ainda não cobertos por uma skill própria (peças que ainda não foram
construídas, ou que têm pouca regra formal além do próprio código):

- **Motor de regras — grupos Visibilidade/Cálculo** (catalogados em
  `core/rules_catalog.py`, sem função JS ainda — `progress_bar` do
  Designer depende disso pra ficar dinâmico)
- Tier 3 de componente do Designer (`tabs`/`accordion`/`chart`/
  `rich_text`/`carousel`) e `screen_generator.py` (gerar página do
  Designer inteira a partir de metadata OData) — ver skill 16, seção 7

A skill 11 (referência fraca / `@display_field` / `@weak_ref`) está em
**[DECIDIDO], pendente de implementação** — investigação direta no
`ChristopherNicolasSMM/PyTeca` real confirmou que `@display_field` já
tinha sido portado (Fase 4) mas nunca usado nem consumido; `@weak_ref`
é anotação nova, sem equivalente no PyTeca (que não tem o conceito de
referência fraca — lá toda relação é FK real).

A skill 15 (pop-ups/diálogos) está em **[DECIDIDO], pendente de
implementação** — nasceu de revisão real do código (`confirm()` nativo
sem estilo, `flash()` duplicado por template, sem centralização em
`base.html`), e é o gatilho para a primeira implementação real do motor
de i18n (skill 00, que até aqui era só regra, nunca teve `t()`/
`i18n_service.py` de fato). Adendas nas skills 00 (motor de i18n) e 01
(`static/` confirmado como global, sem `static/core/`).

A skill 19 (reestruturação do yeast_bank com a entidade `Container`,
entre Dispositivo e Item do banco) está **[EXECUTADA]** — model,
CrudGen e as 6 migrations já estão no código (BACKLOG, Fase 14),
validados ponta a ponta com dados reais. Falta só a tela integrada de
navegação (drill-down container → itens → detalhe), fase própria e
futura.

Cada novo documento deve seguir o mesmo padrão: sem código de implementação,
só regra, schema e exemplo — pronto para ser citado por uma IA ou
desenvolvedor durante a construção.
