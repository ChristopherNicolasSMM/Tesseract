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

## Status

As skills de fundação (nomenclatura, estrutura, parâmetros, documentação)
estão completas e em uso ativo — toda a construção real do Tesseract até
aqui (Core, RBAC, versionamento, CrudGen, `addon_brewstation` com 3
Features/24 entidades, páginas HTML, Roles/Permissions, catálogo de
Transações, Migrations, `addon_device_manager`) seguiu essas regras.

As skills 06 e 07 estão em **fase de decisão** (schema e regra fechados,
implementação ainda não autorizada) — ver o próprio arquivo de cada uma
para o detalhe do que está `[DECIDIDO]` vs. `[ABERTO]`. A skill 08 já
foi **executada** (com duas revisões em relação à proposta original —
ver seção 10 do próprio arquivo).

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

Cada novo documento deve seguir o mesmo padrão: sem código de implementação,
só regra, schema e exemplo — pronto para ser citado por uma IA ou
desenvolvedor durante a construção.
