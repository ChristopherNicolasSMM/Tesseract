# Skills de Padronização do Tesseract

Conjunto de regras obrigatórias para qualquer construção (manual ou via IA)
dentro do projeto Tesseract — fusão de PyTeca (CrudGen, RBAC, versionamento),
BrewStation (motor de descoberta/registro) e DEVStationFlask (persistência
de estado, transações, regras).

Ordem de leitura recomendada:

1. **00-glossario-e-convencoes-gerais.md** — termos (Core/Addon/Plugin/Feature/
   Module/Transação/Hook/CrudGen/Snapshot) e convenções de idioma e casing.
2. **01-nomenclatura-pastas-e-arquivos.md** — estrutura de diretórios do Core,
   de um Addon e de um Plugin; nomenclatura de arquivos e classes.
3. **02-nomenclatura-tabelas-e-prefixos.md** — regra tri-nível de prefixo de
   tabela, convenção de colunas, regra de FK entre módulos.
4. **03-parametros-argumentos-e-manifestos.md** — schema de `addon.json`,
   `feature.json`, `plugin.json`; argumentos da CLI do CrudGen; parâmetros de
   runtime em `system_config`.

## Status

Estas são as skills de **fundação** (nomenclatura, estrutura, parâmetros).
Ainda não cobrem (próximos documentos, a produzir quando você pedir):

- Contrato do Core (`o que nunca pode entrar em core/`, detalhado em regra,
  não só em estrutura)
- RBAC — schema completo de Role/Permission e regras de uso de
  `@permission`
- Versionamento — schema completo de `CodeSnapshot` e triggers
- EventBus — convenção de nomes de evento e contrato de payload
- Motor de regras (rule engine) herdado do DEVStationFlask
- OData/Screen Generator

Cada novo documento deve seguir o mesmo padrão: sem código de implementação,
só regra, schema e exemplo — pronto para ser citado por uma IA ou
desenvolvedor durante a construção real (que ainda não foi autorizada).
