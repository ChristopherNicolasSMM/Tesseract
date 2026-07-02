# 02 — Diagrama C4 (Addon Estoque — Componente)

Nível Componente (skill 04 — nível Addon gera Componente). Contexto/
Container do sistema como um todo fica em `docs/technical/02-diagrama-c4.md`
da raiz — ainda **não atualizado** com a caixa deste Addon (pendência).

```mermaid
C4Component
    title addon_estoque - Componentes

    Container_Boundary(estoque, "addon_estoque") {
        Component(model_material, "Material", "SQLAlchemy model", "Identidade de qualquer item estocavel")
        Component(model_composicao, "Composicao", "SQLAlchemy model", "Auto-relacionamento (BOM/kit)")
        Component(model_mov, "Movimentacao", "SQLAlchemy model", "Ledger imutavel entrada/saida/ajuste")
        Component(model_saldo, "Saldo", "SQLAlchemy model", "Cache materializado 1:1 com Material")

        Component(svc_material, "material_service", "Python service", "CRUD de Material, registrar_movimentacao(), recalcular_saldo()")
        Component(svc_lookup, "material_lookup", "Python service publico", "get_material(id), buscar_material_por_termo(query) - unico ponto de leitura para outros Addons")

        Component(ctrl_material, "controller/materiais.py", "Flask Blueprint", "Rotas web de Material")
        Component(ctrl_mov, "controller/movimentacoes.py", "Flask Blueprint", "Rotas web de Movimentacao/Saldo")
    }

    Rel(ctrl_material, svc_material, "usa")
    Rel(ctrl_mov, svc_material, "usa")
    Rel(svc_material, model_material, "le/escreve")
    Rel(svc_material, model_composicao, "le/escreve")
    Rel(svc_material, model_mov, "le/escreve")
    Rel(svc_material, model_saldo, "le/escreve")
    Rel(svc_lookup, model_material, "le")
    Rel(svc_lookup, model_saldo, "le")
```

## Nota sobre `buscar_material_por_termo`

Método novo no service público, motivado pelo fluxo de resolução de
ingrediente de `feature_mash_control` (busca textual/fuzzy por nome,
não só `get_material(id)`) — ver
`addons/addon_brewstation/features/feature_mash_control/docs/technical/03-fluxos.md`.

## Nota sobre consumidores externos

`svc_lookup` é o único ponto de entrada pra qualquer Addon externo.
Nenhum Addon externo importa `model_material`/`model_saldo`
diretamente — sempre passa pelo service público, mesmo em leitura.
