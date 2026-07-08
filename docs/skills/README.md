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
em Transaction) também já foi **executada**.

Ainda não cobertos por uma skill própria (peças que ainda não foram
construídas, ou que têm pouca regra formal além do próprio código):

- **EventBus** — convenção de nomes de evento e contrato de payload (hoje
  só `core.module.activated` existe; código já segue namespace por ponto,
  reaproveitado pela skill 08 para nome de logger — mas o EventBus em si
  ainda não tem skill dedicada)
- **Motor de regras** (validação/visibilidade/cálculo, herdado do
  DEVStationFlask) — Fase 7b, não iniciada
- **Designer visual drag-and-drop** — Fase 7c, não iniciada
- **OData/Screen Generator** — Fase 8, não iniciada

A skill 11 (referência fraca / `@display_field` / `@weak_ref`) está em
**[DECIDIDO], pendente de implementação** — investigação direta no
`ChristopherNicolasSMM/PyTeca` real confirmou que `@display_field` já
tinha sido portado (Fase 4) mas nunca usado nem consumido; `@weak_ref`
é anotação nova, sem equivalente no PyTeca (que não tem o conceito de
referência fraca — lá toda relação é FK real).

Cada novo documento deve seguir o mesmo padrão: sem código de implementação,
só regra, schema e exemplo — pronto para ser citado por uma IA ou
desenvolvedor durante a construção.
