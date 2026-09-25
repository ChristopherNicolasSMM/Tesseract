# 03 — Fluxos (Feature Envase)

## Caminho feliz: registro de Envase → Composição → baixa síncrona

```mermaid
sequenceDiagram
    participant User as Usuário
    participant UI as Tela Envase
    participant EnvSvc as envase_estoque_service
    participant IngSvc as ingredient_consumption_service (feature_mash_control)
    participant Lookup as material_lookup (addon_estoque)
    participant Envase as tesseract_brewstation_env_envase
    participant EstSvc as estoque_service (addon_estoque)
    participant Saldo as tesseract_estoque_saldo

    User->>UI: Registra envase do Lote X (Material resultante + litros)
    UI->>EnvSvc: registrar_envase(lote_id, material_resultante_id, quantidade_litros)
    EnvSvc->>Lookup: get_material(material_resultante_id)
    Lookup-->>EnvSvc: volume_real (obrigatório — sem ele, VolumeRealNaoConfiguradoError)

    alt lote.insumos_baixados_em is None
        EnvSvc->>IngSvc: confirmar_consumo_ingredientes(lote_id)
        Note over EnvSvc,IngSvc: fallback — nunca deixa um Envase<br/>acontecer sem custo de insumo rastreado
        IngSvc-->>EnvSvc: custo_total_insumos gravado em BrewSession
    end

    EnvSvc->>Envase: INSERT envase (lote_id, material_resultante_id, quantidade_litros, ...)
    EnvSvc->>Lookup: get_composicao(material_resultante_id)
    Lookup-->>EnvSvc: [{material_componente_id, quantidade}, ...]

    loop para cada componente da Composição
        EnvSvc->>EnvSvc: quantidade_total = componente.quantidade * (litros / volume_real)
        EnvSvc->>EstSvc: registrar_movimentacao(material_componente_id, "saida", quantidade_total)
        EstSvc->>Saldo: atualiza quantidade_atual
    end

    EnvSvc-->>UI: envase confirmado, unidades_geradas, componentes_baixados
```

`ItemEnvase` não é mais criado em nenhum passo deste fluxo — os
componentes vêm inteiramente da Composição do Material resultante.

## Cálculo de custo de industrialização (sob demanda, não no registro)

```mermaid
sequenceDiagram
    participant User as Usuário/API
    participant EnvSvc as envase_estoque_service
    participant Envase as tesseract_brewstation_env_envase
    participant Lookup as material_lookup (addon_estoque)

    User->>EnvSvc: calcular_custo_industrializacao_envase(envase_id)
    EnvSvc->>Envase: soma quantidade_litros de todos os Envases do mesmo lote_id
    Note over EnvSvc: custo_cerveja = (BrewSession.custo_total_insumos / litros_do_lote)<br/>* quantidade_litros deste Envase
    EnvSvc->>Lookup: get_composicao(material_resultante_id)
    loop para cada componente
        EnvSvc->>Lookup: get_saldo(material_componente_id) -> custo_medio
        Note over EnvSvc: custo_linha = quantidade_total * custo_medio
    end
    EnvSvc-->>User: {custo_cerveja, custo_componentes, custo_total_industrializacao, detalhe_componentes}
```

Este cálculo não grava nada — pode ser chamado quantas vezes quiser,
a qualquer momento depois do Envase existir (mesmo raciocínio de
"cálculo separado de commit" já usado em
`ingredient_consumption_service.calcular_custo_insumos_receita()`).

## Precificação de venda: simula → calcula-e-salva → vincula (mecanismo separado)

> Ver `01-visao-geral.md`, seção "Dois mecanismos de custo", para a
> diferença em relação ao cálculo de industrialização acima — este
> fluxo tem tela própria (`controller/precificacao.py`) e persiste
> resultado; o de industrialização não.

```mermaid
sequenceDiagram
    actor User as Usuário
    participant UI as Tela Precificação
    participant Svc as precificacao_service
    participant MC as RecipeIngredient (feature_mash_control)
    participant Saldo as addon_estoque.Saldo
    participant Padrao as PrecoPadraoInsumo (feature_ingredientes)
    participant DB as CalculoPrecificacao / ItemCustoIngrediente

    User->>UI: Escolhe Lote + % lucro + % IPI + % ICMS ("Simular")
    UI->>Svc: simular(lote_id, envase_id=None, ...)
    loop cada RecipeIngredient da receita do Lote
        Svc->>Saldo: custo_medio do material_id?
        alt tem Saldo real
            Saldo-->>Svc: preco_unitario (origem_preco="real")
        else Material é malte/lúpulo/levedura
            Svc->>Padrao: valor_padrao do tipo_insumo
            Padrao-->>Svc: preco_unitario (origem_preco="padrao")
        else
            Svc-->>Svc: preco_unitario=0.0 (origem_preco="sem_preco" — nunca escondido)
        end
        Svc->>Svc: converter_quantidade(quantidade da receita -> unidade do preço)
        Svc->>Svc: custo_total += preco_unitario * quantidade_convertida
    end
    Svc->>Svc: aplica % lucro sobre subtotal, depois % IPI/ICMS sobre (subtotal + lucro)
    Svc-->>UI: resultado completo (não persistido)

    User->>UI: "Confirmar" (decide seguir com este número)
    UI->>Svc: calcular_e_salvar(lote_id, envase_id, ...) — recalcula do zero, não reaproveita a simulação
    Svc->>DB: INSERT CalculoPrecificacao + N ItemCustoIngrediente
    DB-->>Svc: calculo.id

    opt Envase já existe
        User->>Svc: vincular_envase(calculo_id, envase_id)
        Svc->>DB: UPDATE CalculoPrecificacao.envase_id
    end
```

**Achados reais deste fluxo:**

- **`simular()` e `calcular_e_salvar()` recalculam do zero, cada um**
  — `simular()` não retorna um id reaproveitável; confirmar depois de
  simular dispara a mesma conta de novo, não só grava o que já foi
  calculado. Se o preço de algum insumo mudar entre o clique em
  "Simular" e o clique em "Confirmar", o valor salvo pode diferir do
  que foi mostrado na simulação.
- **Custo de embalagem depende de `envase_id` ser passado** — sem
  Envase ainda (simulação antes de decidir embalar), `custo_embalagem_total`
  é sempre `0.0`, não por falta de preço, mas porque não há
  `ItemEnvase` para somar. Ver o achado sobre `ItemEnvase` estar
  congelado desde a skill 26, na seção acima (`01-visao-geral.md`).
- **Ordem de aplicação dos percentuais**: lucro incide sobre
  `subtotal` (ingredientes + embalagem); IPI e ICMS incidem sobre
  `subtotal + lucro` — nunca em cascata um sobre o outro (`valor_ipi`
  e `valor_icms` são calculados separadamente, ambos sobre a mesma
  base, depois somados).
- **`_material_display()` resolve nome, nunca id** — correção da
  última sessão real antes desta auditoria (commit
  "mostra nome do Material (não id)"); a tela de resultado usa
  `material_lookup.get_material()` para mostrar o nome do insumo, não
  o `material_id` cru.

## Transação de confirmação (2026-09-25)

`EnvaseService.create_override` delega a `envase_estoque_service.registrar_envase`. A função chama `confirmar_consumo_ingredientes(commit=False)` quando necessário, grava o Envase com `flush`, chama `registrar_movimentacao(commit=False)` para cada componente e só então executa um `commit`. Qualquer erro reverte todo o conjunto. O CRUD gerado usa hooks de serviço para impedir update/trash/restore/delete e a tela de detalhe apenas consulta o registro; a API compartilha os mesmos hooks. O fluxo de estorno permanece pendente e deve escrever movimentações compensatórias, sem alterar as originais.
