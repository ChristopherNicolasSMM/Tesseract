# 04 — Modelo de Dados (Feature Brew Father)

Sem tabela de domínio própria. Único model previsto — ainda não
implementado — é o log de sincronização:

```mermaid
erDiagram
    BREWFATHER_SYNC {
        int id PK
        string tipo_sync "recipes | batches | inventory | all"
        string status "sucesso | erro | parcial"
        int quantidade_processada
        int quantidade_erro
        json raw_data "payload bruto, so p/ auditoria/debug"
        string mensagem_erro
        datetime iniciado_em
        datetime finalizado_em
    }
```

Tabela real prevista: `tesseract_brewstation_brewfather_sync`.
