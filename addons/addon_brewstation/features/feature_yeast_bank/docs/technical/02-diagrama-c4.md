# 02 — Diagrama C4 (Feature Yeast Bank — Componente)

```mermaid
C4Component
    title feature_yeast_bank — Componentes

    Component(strain, "YeastStrain", "Model", "Cepa — parâmetros de decaimento de viabilidade")
    Component(device, "YeastStorageDevice", "Model", "Dispositivo físico — freezer/geladeira/câmara")
    Component(container, "YeastContainer", "Model", "Caixa/estante dentro de um Dispositivo (skill 19)")
    Component(item, "YeastBankItem", "Model", "Item físico do banco — onde a viabilidade ESTIMADA vive")
    Component(history, "YeastCellCountHistory", "Model", "Contagens reais e estimadas — cálculo de Neubauer (skill 22)")
    Component(event, "YeastBankEvent", "Model", "Ponto de entrada único (skill 21) — Starter fundido aqui (skill 22)")
    Component(config, "YeastBankConfig", "Model", "Decaimento/validade/alerta por tipo de armazenamento (skill 19/21)")
    Component(viability, "viability_engine.py", "Service", "Motor de estimativa — não é CRUD genérico")
    Component(tool, "yeast_bank_viability.py (controller)", "Flask", "Tela de ação em lote")
    Component(painel, "yeast_bank_painel.py (controller)", "Flask", "Tela integrada de navegação (skill 21)")

    Rel(item, strain, "usa parâmetros de modelo de decaimento")
    Rel(item, container, "está guardado em")
    Rel(container, device, "pertence a")
    Rel(event, item, "origina-se de")
    Rel(event, history, "cria automaticamente (Contagem de Células)")
    Rel(viability, item, "lê referência (contagem/starter/cepa), grava estimativa")
    Rel(viability, config, "usa decaimento/alerta do storage_type do item")
    Rel(tool, viability, "dispara recalculate_all()")
    Rel(painel, item, "consulta via API REST")
    Rel(painel, event, "consulta/cria via API REST")
```
