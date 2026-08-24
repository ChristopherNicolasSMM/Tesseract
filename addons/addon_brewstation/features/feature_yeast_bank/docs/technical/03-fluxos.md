# 03 — Fluxos (Feature Yeast Bank)

## Caminho feliz: recalcular viabilidade

```mermaid
flowchart TD
    A[POST /brewstation/yeast-bank-tools/recalculate-viability] --> B[Para cada YeastBankItem]
    B --> C{Status descartado/contaminado?}
    C -->|Sim| D[Pula — marca skipped]
    C -->|Não| E[Busca melhor referência]
    E --> F{Achou referência?}
    F -->|Não| G[Marca no_reference]
    F -->|Sim| H[Existe YeastBankConfig ativa pro storage_type do item?]
    H -->|Sim, com decaimento| I[Usa daily_viability_loss_pct da config]
    H -->|Não| J[Usa daily_viability_loss_pct da cepa]
    I --> K[Aplica modelo linear]
    J --> K
    K --> L[Grava estimated_viability_pct + metadados de referência]
    L --> M[commit]
```

Modelo exponencial removido (skill 21) — sempre linear.

## Prioridade de referência (dentro de "Busca melhor referência")

```mermaid
flowchart LR
    A[Histórico real] -->|não achou| B[Histórico estimado]
    B -->|não achou| C[Starter]
    C -->|não achou| D[Valor inicial da cepa]
    D -->|não achou| E[Sem referência]
```

Todas as consultas excluem registros com `contamination_detected=True`.

## Criação de `YeastBankItem` — validade automática (skill 21)

```mermaid
sequenceDiagram
    participant U as Usuário
    participant C as Controller (create/update)
    participant H as yeast_bank_item_service_hooks.pai_apply_fields
    participant Cfg as YeastBankConfig

    U->>C: POST (sem expiry_date preenchido)
    C->>H: chama depois de aplicar os campos
    H->>H: expiry_date já veio preenchido?
    alt expiry_date vazio E prepared_date presente
        H->>Cfg: busca config ativa pro storage_type do item
        Cfg-->>H: expiry_days (se existir)
        H->>H: expiry_date = prepared_date + expiry_days
    end
    H-->>C: segue o fluxo normal (commit)
```

Nunca sobrescreve um `expiry_date` já informado manualmente.

## `YeastBankEvent` como ponto de entrada único (skill 21)

`YeastBankEvent` é o único lugar onde Starter e Contagem de Células
podem ser criados — as telas próprias delas bloqueiam a criação
direta (`block_create`, controller hook) e só permitem editar/
consultar registros já existentes.

```mermaid
sequenceDiagram
    participant U as Usuário
    participant C as Controller (create de bank_event)
    participant H as yeast_bank_events_hooks.post_create_redirect
    participant Starter as YeastStarterLog
    participant Count as YeastCellCountHistory

    U->>C: POST /yeast-bank-events (event_type, bank_item_id)
    C->>C: cria o YeastBankEvent normalmente
    C->>H: chama depois do commit bem-sucedido
    alt event_type == "Starter"
        H->>Starter: cria vinculado ao mesmo bank_item_id
        H->>C: event.starter_id = starter.id, commit
        H-->>C: redirect() pra edição do Starter
    else event_type == "Contagem de Células"
        H->>Count: cria vinculado ao mesmo bank_item_id
        H->>C: event.cell_count_id = count.id, commit
        H-->>C: redirect() pra edição da Contagem
    else event_type == "Descarte"
        H->>H: event.status_before = bank_item.status (captura o status atual)
        H->>H: bank_item.status = event.status_after (ou "discarded" se vazio)
        H->>C: commit — item e evento atualizados juntos
        H-->>C: None — sem tela especializada, fica no manage() padrão
    else Outro
        H-->>C: None — sem efeito nenhum além do próprio registro
    end
```

`status_before` é `@readonly_fields` — mesmo que alguém tente mandar
esse campo direto via POST/JSON, `service.py.j2::_apply_fields` ignora
(reanálise de 2026-08-24: a primeira versão só protegia o formulário,
não a API — corrigido pra proteger os dois a partir da mesma fonte,
`get_readonly_fields()`).

O mesmo hook roda na rota web **e** na API JSON — na API só o efeito
colateral (criar o registro vinculado, ou aplicar a mudança de
status) importa, o valor de retorno (um redirect do Flask) é
descartado.

## Alerta de validade/viabilidade baixa (reanálise 2026-08-24)

Decisão do Christopher: só sinaliza pra tela, **não cria** `YeastBankEvent`
nem dispara nenhuma notificação.

```mermaid
sequenceDiagram
    participant U as Usuário/API
    participant Item as YeastBankItem.to_dict()
    participant Eng as viability_engine.compute_alert_flags()
    participant Cfg as YeastBankConfig

    U->>Item: GET (lista ou detalhe)
    Item->>Eng: chamado a cada to_dict() — sob demanda, nunca persistido
    Eng->>Cfg: busca config ativa pro storage_type do item
    alt sem config
        Eng-->>Item: {expiry_alert: false, low_viability_alert: false}
    else com config
        Eng->>Eng: dias até expiry_date <= alert_days_before_expiry?
        Eng->>Eng: estimated_viability_pct <= alert_min_viability_pct?
        Eng-->>Item: flags calculados na hora
    end
    Item-->>U: JSON com expiry_alert/low_viability_alert
```

Cada condição é independente — um item pode disparar só uma, as duas,
ou nenhuma. Calculado sob demanda em vez de persistido: sempre reflete
o estado atual, nunca fica desatualizado entre execuções do
"Recalcular Viabilidade" — o trade-off é 1 query extra
(`YeastBankConfig`) por item exibido, mesmo padrão de custo que
`weak_ref_display` já tem na listagem (skill 11).

## Tentativa de criar Starter/Contagem direto na tela própria (bloqueada)

```mermaid
sequenceDiagram
    participant U as Usuário
    participant C as Controller (create de starter_log)
    participant H as yeast_starter_logs_hooks.block_create

    U->>C: POST /yeast-starter-logs (tentativa direta)
    C->>H: chama antes de qualquer outra coisa
    H-->>C: mensagem de erro (string)
    C-->>U: flash da mensagem + redirect pra lista — nada é criado
```

