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
8. **07-menu-personalizacao-e-hierarquia.md** — menu completo: ordem/
   colapso por nó com padrão global (admin) e override por usuário, e
   estrutura em árvore de profundidade arbitrária (`parent_id`/
   `order_index` em `Transaction`, substitui o campo `group` plano).
   Fusão dos antigos documentos 07 e 10 (consolidação 2026-09) — o
   arquivo `10-menu-hierarquico.md` não existe mais, seu conteúdo vive
   aqui; o número "10" fica vago (não reaproveitado, ver nota abaixo).
9. **08-logging-observabilidade-e-administracao.md** — convenção de nome
   de logger, separação de camadas de log (rotina vs. erro grave) com
   enforcement técnico, formato de console, log global do Core (`logs/`
   na raiz), e tela administrativa de consulta/exclusão de logs (RBAC
   padrão, sem tier separado).
10. **09-auto-descoberta-modulos.md** — descoberta automática de rotas/
    models/menu via `pkgutil.walk_packages`, escopada por Addon/Feature
    (adaptação do mecanismo real do PyTeca à arquitetura tri-nível).
11. **11-referencia-fraca-e-display-field.md** — resolução de campo de
    referência fraca (skill 02) em nome legível na tela gerada e em
    combo de busca, via `@display_field`/`@weak_ref` + geração
    automática pelo CrudGen + `/api/options/<table>`.
12. **12-crudgen-referencia-e-operacao.md** — referência completa do
    CrudGen (pipeline model→CLI→arquivos, guia de uso de cada
    anotação: `@label`/`@plural`/`@choices`/`@required`/`@max_length`/
    `@min_length`/`@min_value`/`@display_field`/`@weak_ref`/
    `@menu_icon`/`@permission`, semântica de hooks/`--overwrite`/
    `--only templates`, migração de 3 módulos reais pro caminho de
    auto-descoberta — skill 09) **+** guia operacional (fluxo de
    objetos completo request→controller→service→model→DB, Web e API,
    com a assimetria real de `manage()` não passar pelo
    `Service.list()`; os únicos 2 pontos reais de hook de lifecycle —
    `pbo_apply_fields`/`pai_apply_fields`, só em create/update; checklist
    de "como adicionar um campo"; cookbook de manutenções comuns).
    Fusão dos antigos documentos 12 e 13 (consolidação 2026-09) — o
    arquivo `13-crudgen-guia-operacional.md` não existe mais, seu
    conteúdo vive aqui (seções 8–12); número "13" fica vago.
13. **14-eventbus-convencao.md** — convenção de nome de evento e
    contrato de payload do EventBus (`core/event_bus.py`), catálogo
    real dos 2 eventos em uso hoje, e 2 achados de manutenção (nome de
    evento duplicado como string literal em publisher/subscriber;
    docstring desatualizada em `register_example_listener()`).
14. **15-popups-e-dialogos-padrao.md** — padrão de diálogo de
    confirmação e toast/alert (Core), substituindo `confirm()`/
    `alert()` nativos e o `flash()` duplicado por template; primeiro
    uso real do motor de resolução de i18n (adendo da skill 00),
    delegação de evento obrigatória para sobreviver a fragmento AJAX
    (Plant Workspace/Dashboard).
15. **16-designer-paginas-customizadas.md** — três documentos fundidos
    (consolidação 2026-09): (a) o que resta do Designer visual — Ações
    (catálogo em duas camadas: código + `DesignerDataAction`, sempre
    server-side quando toca dado), Provedor OData local
    (`@odata_expose`, atalho em processo), Tier 1/2 de componente
    (histórico — construtor removido na Fase 12) e substituição de
    tela do CrudGen no menu (`replace_in_menu`); (b) como uma página
    customizada consome dado — os três caminhos (API REST do CrudGen,
    Ação de Dado, `/api/options/`), contratos, permissão (401 vs 403),
    segurança (SSTI, XSS, CSRF) e erros comuns; (c) estrutura/convenção
    dos modelos `/freestyle/` (Fase 13) — onde controller/template/JS
    moram, por que `templates/` não é servível, convenção de nome
    `model_X-*.js` vs. `freestyle-*.js`, passo a passo para criar um
    modelo novo. Modelos estáticos em
    `static/modelo_paginas_nice_admin/_modelo-pagina-{basico,completo}.html`
    também existem, decisão de consolidação com `/freestyle/` em
    aberto (BACKLOG, Fase 13). Os arquivos `17-paginas-customizadas-
    fluxo-de-dados.md` e `18-freestyle-modelos-de-referencia.md` não
    existem mais; números "17" e "18" ficam vagos.
16. **19-proposta-reestruturacao-yeast-bank-container.md** — nova
    entidade `YeastContainer` entre Dispositivo e Item do banco
    (Dispositivo 1:N Container 1:N Item), remoção de
    `YeastBankItem.storage_device_id` em favor de `container_id`,
    plano de migration em 6 passos sem perda de dado, e navegação em
    drill-down proposta para a futura tela integrada (BACKLOG, Fase
    14). Model, CrudGen e as 6 migrations já implementados; falta só
    a tela integrada de navegação.
17. **20-proposta-crudgen-tipo-sqlalchemy-html.md** — `_FIELD_HTML_VALIDATIONS`
    (skill 12) ganhou `html_type` via introspecção real de
    `db.Date`/`DateTime`/`Time`/`Integer`/`Float`/`Numeric`/`Boolean`/
    `Text`, mantendo `@enum_field`/`@weak_ref` com prioridade. Sem
    `@calendar` nova. **Executada.**
18. **21-tela-integrada-navegacao-unificacao-evento-starter-contagem.md** —
    `YeastBankEvent` vira ponto de entrada único (Starter/Contagem de
    Células criam registro especializado automaticamente e
    redirecionam); `YeastStorageReading` removida;
    `strain_id`/`starter_id` redundantes removidos de
    `bank_event`/`cell_count_history`; hooks de controller
    (`block_create`/`post_create_redirect`) ficaram reais pela
    primeira vez. **Executada por completo** (BACKLOG Fases 20 e 22
    — schema/fluxo e a tela integrada em si).
19. **22-fusao-starter-bankevent-neubauer.md** — `YeastStarterLog`
    removida, fundida direto em `YeastBankEvent` (decisão do
    Christopher: opção B, fusão total, entre as duas apresentadas);
    `YeastCellCountHistory` ganha `bank_event_id` (rastreio de
    origem) e campos brutos de entrada da câmara de Neubauer, com
    cálculo automático (`cells_per_ml`/`viability_percent`/
    `viable_cells_per_ml`). **Executada** (BACKLOG Fase 26) —
    3 migrations com migração real de dado existente (starter_log →
    bank_event antes de dropar a tabela).
20. **23-proposta-expansao-addon-estoque.md** — taxonomia (Origem/
    TipoProduto/Categoria), fracionamento (`MaterialUnidade`/
    `fator_para_base`), cadastro de Fornecedor/Transportadora/Endereço
    (referência fraca, sem dono fixo) e Pedido de Compra com Entrada
    de Mercadoria. 4 fases entregues.
21. **24-proposta-sistema-cotacao-rfq.md** — sistema de cotação
    (RFQ) inspirado em SAP MM: `ItemProcessoCotacao` (item pedido uma
    vez por processo) + `Cotacao`/`ItemCotacao` (resposta por
    fornecedor), seleção de vencedor, geração de Pedido de Compra a
    partir da cotação. 3 fases (6.1/6.2/6.3) entregues.
22. **25-proposta-acoes-em-massa-padrao-crudgen.md** — apagar/
    inativar em massa vira padrão gerado pelo CrudGen; novo mecanismo
    de "hook de template" (`_acoes_em_massa_extra.html`/
    `_detail_extra.html`); aplicação em Malte/Lúpulo/Levedura/
    MashRecipe/Material, estendida depois a Fornecedor/Transportadora.
23. **26-proposta-envase-consumo-insumo-custo-industrializacao.md** —
    `Envase` passa a referenciar o Material resultante (produto
    acabado) em vez de `ItemEnvase` digitado à mão (resolvido via
    Composição); consumo de insumo da receita na brassagem (botão
    "Confirmar Ingredientes", idempotente); custo real de
    industrialização.
24. **27-proposta-sincronizacao-seletiva-brewfather.md** — tela de
    seleção prévia (checkbox) antes de importar receitas do
    BrewFather, já que a API não suporta filtro por tag/pasta no
    servidor; sinalização de status (nova/já importada/apagada
    pendente de reimportar).

## Status

As skills de fundação (00–04: nomenclatura, estrutura, parâmetros,
documentação) estão completas e em uso ativo — toda a construção real
do Tesseract seguiu essas regras.

### Skills 05–27 — todas executadas

Todas as skills numeradas de 05 a 27 estão **[EXECUTADO]** no código
real, confirmado sessão a sessão. Consolidado aqui (2026-09-01) porque
vários cabeçalhos individuais tinham ficado presos num status antigo
mesmo depois de implementados — achado durante uma auditoria geral do
conjunto (ver BACKLOG.md); os próprios arquivos já foram corrigidos,
isso aqui é só o resumo:

| Skill | Executada | Observação |
|---|---|---|
| 05 — Device Manager / MQTT vs. EventBus | Sim | Fases F/G (validação com hardware real, docs finais) ficam fora do repositório principal |
| 06 — Model Builder / Playground | Sim | — |
| 07 — Menu: Personalização e Hierarquia | Sim | Fusão dos antigos documentos 07 (ordem/colapso) e 10 (árvore N-níveis) na consolidação de 2026-09 — número "10" vago, não reaproveitado |
| 08 — Logging/Observabilidade | Sim | Com revisões registradas no próprio arquivo |
| 09 — Auto-Descoberta de Módulos | Sim | Cabeçalho corrigido nesta auditoria (dizia "fase de decisão") |
| 11 — Referência Fraca / `@display_field` | Sim | — |
| 12 — CrudGen Referência e Operação | Referência viva | Fusão dos antigos documentos 12 (o que existe — seção 3 corrigida nesta auditoria, dizia "8 artefatos", são 10 desde a skill 25) e 13 (como trabalhar), consolidação 2026-09 — número "13" vago, não reaproveitado |
| 14 — EventBus Convenção | Referência viva | — |
| 15 — Pop-ups e Diálogos | Sim | Cabeçalho corrigido nesta auditoria (dizia "execução pendente") |
| 16 — Designer, Páginas Customizadas e Freestyle | Sim | Fusão dos antigos documentos 16 (Designer — construtor visual removido na Fase 12, ver nota no próprio arquivo), 17 (páginas customizadas) e 18 (Freestyle), consolidação 2026-09 — números "17"/"18" vagos |
| 19 — Yeast Bank Container | Sim | Tela integrada (item que faltava) fechada pelas skills 21/22 |
| 20 — CrudGen tipo SQLAlchemy | Sim | — |
| 21 — Tela Integrada Yeast Bank | Sim | Seção 1 parcialmente superada pela skill 22 (mesmo dia) — ver nota no próprio arquivo |
| 22 — Fusão Starter/BankEvent/Neubauer | Sim | Continuação direta da 21 |
| 23 — Expansão Addon Estoque | Sim | 4 fases entregues |
| 24 — Sistema de Cotação (RFQ) | Sim | 3 fases entregues |
| 25 — Ações em Massa (CrudGen) | Sim | Cabeçalho corrigido nesta auditoria (dizia "planejamento fechado, implementação não iniciada") — estendida depois a Fornecedor/Transportadora |
| 26 — Envase / Custo de Industrialização | Sim | — |
| 27 — Sync Seletiva BrewFather | Sim | — |

**"Referência viva"** (12, 14) significa que não há uma "execução"
pontual pra marcar — são documentos descritivos do que já existe,
atualizados conforme o próprio mecanismo evolui (ex.: skill 12 seção 3
mudou de 8 pra 10 artefatos quando a skill 25 acrescentou os hooks de
template).

### Consolidação de legibilidade (Fase 1, 2026-09)

Auditoria pedida por Christopher para reduzir repetição e melhorar a
leitura das skills 00–18 (convenção geral), **sem alterar nenhuma
regra** — só reorganização/fusão de documentos que cobriam a mesma
superfície em momentos diferentes. Skills 05 e 19–27 (propostas de
iniciativa, com histórico de decisão citável em commits/BACKLOG) ficam
de fora da fusão — só recebem limpeza de legibilidade interna, nunca
troca de nome de arquivo.

Números de arquivo fundidos **não são reaproveitados** — evita
referência cruzada antiga (código, commit, BACKLOG) apontar para um
conteúdo diferente do que apontava originalmente.

| Fusão | Status |
|---|---|
| 07 (menu personalização) + 10 (menu hierárquico) → `07-menu-personalizacao-e-hierarquia.md` | **Feita** |
| 12 (CrudGen referência) + 13 (CrudGen guia operacional) → `12-crudgen-referencia-e-operacao.md` | **Feita** |
| 16 (Designer) + 17 (páginas customizadas) + 18 (Freestyle) → `16-designer-paginas-customizadas.md` | **Feita** |
| 00–06, 08, 09, 11, 14, 15 | Sem fusão — só limpeza interna (Opção A), a confirmar arquivo por arquivo durante a auditoria |

### Peças ainda sem skill própria

Não construídas, ou com pouca regra formal além do próprio código:

- **Motor de regras — grupos Visibilidade/Cálculo** (catalogados em
  `core/rules_catalog.py`, sem função JS ainda — `progress_bar` do
  Designer depende disso pra ficar dinâmico).
- **Tier 3 de componente do Designer** (`tabs`/`accordion`/`chart`/
  `rich_text`/`carousel`) e `screen_generator.py` (gerar página do
  Designer inteira a partir de metadata OData) — ver skill 16, seção 7.
- **`detail.html` com abas complexas** (`pedido_compras`/
  `processo_cotacaos`) — investigado na sessão de 2026-09-01 (skill 25,
  extensão): não cabe no hook de `_detail_extra.html` existente (esse
  só sabe *anexar depois*; aqui o form genérico foi *reorganizado em
  abas*, precisaria de um hook de "substituição completa", não
  implementado). Registrado como pendência no BACKLOG.md, não em skill
  própria ainda.
- **Modelos estáticos legados** (`static/modelo_paginas_nice_admin/
  _modelo-pagina-{basico,completo}.html`) — decisão de consolidação
  com `/freestyle/` (skill 16) ainda em aberto (BACKLOG, Fase 13).

Cada novo documento deve seguir o mesmo padrão: sem código de
implementação, só regra, schema e exemplo — pronto para ser citado por
uma IA ou desenvolvedor durante a construção.

Cada skill formalizada como proposta (05, 06, 19–27) segue a mesma
convenção de status interna: **[DECIDIDO]** (fechado, pronto pra
executar), **[EXECUTADO]** (já no código) e **[ABERTO]** (ainda sem
decisão) — definida uma vez na skill 05 e reaproveitada nas demais sem
precisar redefinir a cada documento novo.
