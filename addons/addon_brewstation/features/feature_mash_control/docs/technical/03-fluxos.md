# 03 — Fluxos (Feature Mash Control)

## Caminho feliz: sessão de brassagem (manual, sem automação)

```mermaid
flowchart TD
    A[Cadastrar Receita] --> B[Cadastrar Planta + Vasilhames]
    B --> C[Mapear Vasilhame a uma DeviceFunction]
    C --> D[Criar Sessão de Brassagem]
    D --> E[Registrar Passos manualmente]
    E --> F[Registrar Logs/Alarmes conforme necessário]
    F --> G[Marcar sessão como concluída]
```

## Sequência: regra de automação (definição apenas, sem execução)

```mermaid
sequenceDiagram
    actor U as Usuário
    participant Rule as AutomationRule
    participant Lookup as device_function_lookup (addon_device_manager, service público)

    U->>Rule: cria regra (sensor, condição, atuador, ação)
    Rule->>Lookup: referencia sensor_function_id/actor_function_id (referência fraca, cross-Addon)
    Note over Rule: fica registrada — NENHUM motor avalia continuamente ainda
```

## Sequência: importação de receita + resolução de ingrediente (novo)

```mermaid
sequenceDiagram
    actor U as Usuário
    participant Importer as feature_brew_father (ou futuro importador)
    participant Resolve as ingredient_resolution_service
    participant Mapping as IngredientMapping (cache de-para)
    participant Lookup as material_lookup (addon_estoque, service público)
    participant Recipe as MashRecipe (nova versão)
    participant Ingr as RecipeIngredient

    Importer->>Importer: faz parse do formato de origem (API BrewFather/BeerSmith, arquivo BeerXML)
    Importer->>Recipe: cria nova versão (name+versao únicos, origem_receita, origem_receita_id)

    loop para cada ingrediente do parse
        Importer->>Resolve: resolver_ingrediente(origem_receita, descricao, quantidade, unidade)
        Resolve->>Mapping: consulta cache (origem_receita, descricao)
        alt já mapeado antes
            Mapping-->>Resolve: material_id conhecido
            Resolve->>Ingr: INSERT RecipeIngredient (material_id preenchido, status="resolvido")
        else não mapeado
            Resolve->>Lookup: buscar_material_por_termo(descricao)
            alt encontrado
                Lookup-->>Resolve: candidatos
                Resolve->>Ingr: INSERT RecipeIngredient (status="pendente_depara", descricao_origem mantida)
                Note over Resolve: usuário confirma manualmente qual candidato é o certo (de-para)
            else não encontrado
                Resolve->>Ingr: INSERT RecipeIngredient (status="pendente_depara", material_id nulo)
                Note over U: usuário decide: de-para manual OU cadastrar Material novo via addon_estoque
            end
        end
    end

    U->>Mapping: confirma de-para (grava origem_receita+descricao -> material_id, reaproveitado nas próximas importações)
```

## Sequência: nova versão de receita ao salvar edição

```mermaid
sequenceDiagram
    actor U as Usuário
    participant UI as Tela Receita
    participant Recipe as MashRecipe
    participant Hist as RecipeHistory

    U->>UI: edita Receita existente e salva
    UI->>Recipe: INSERT nova linha (mesmo name, versao = versao_atual + 1)
    Note over Recipe: versão anterior nunca é alterada — imutável após criada
    UI->>Hist: INSERT snapshot_data (JSON completo da nova versão + ingredientes)
    Hist-->>UI: registro de histórico disponível pra comparação
```
