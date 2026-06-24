# 01 — Visão Geral (Feature Mash Control)

## Propósito

Receitas (`MashRecipe`), plantas/equipamentos (`BrewPlant`,
`BrewPlantVessel`, `BrewPlantMapping`), sessões de brassagem
(`BrewSession`, `BrewSessionStep`, `BrewSessionLog`,
`BrewSessionAlarm`), dashboards visuais (`DashboardLayout`,
`DashboardWidget`) e regras de automação (`AutomationRule`,
`AutomationRuleLog`).

Portado de `plugin_mash_control` (BrewStation original) — **escopo
deliberadamente CRUD nesta fase** (decisão registrada no
BACKLOG.md). O BrewStation original tinha um repositório com **dois
`plugin.py` e duas pastas de model concorrentes** (sobra de uma
tentativa anterior incompleta) — a fonte real era `model/
mash_models.py`; o resto foi descartado. `Recipe` (modelo legado
duplicado de `MashRecipe`) também foi descartado por decisão
explícita.

## Fora do escopo desta fase (decisão registrada)

A lógica de controle em tempo real do BrewStation original —
controlador PID (`engine/control/pid_controller.py`), motor de
automação que avalia sensores continuamente
(`services/automation_engine.py`), scheduler de processo
(`engine/process/mash_process_engine.py`) — **não foi portada**. As
tabelas migradas armazenam só os *parâmetros* (ex.: `pid_kp`/`pid_ki`/
`pid_kd` em `BrewSessionStep`) e o *estado* (ex.: `status` em
`BrewSession`); o motor que de fato lê sensor, calcula e aciona atuador
em loop fica para uma fase futura, quando o Tesseract tiver um
mecanismo de execução em background (job runner/scheduler) — hoje não
existe.

## Dependências

`feature_device_manager` — `BrewPlantMapping`, `DashboardWidget` e
`AutomationRule` referenciam `DeviceFunction` via FK cross-Feature
(mesmo Addon, permitido — skill 02, clarificação desta fase).

## Tabelas

12 tabelas, prefixo `tesseract_brewstation_mashctrl_*`. Ver
`docs/technical/04-modelo-de-dados.md` (a criar com o ER completo,
junto da Fase 6 de revisão de documentação).
