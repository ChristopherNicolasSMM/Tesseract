# 06 — Manutenção e Expansão (Feature Mash Control)

## Sobre o motor de controle em tempo real (não portado)

O BrewStation original tinha PID controller, motor de automação
(avalia sensor continuamente) e scheduler de processo — todos
dependem de execução em background, que o Tesseract não tem ainda
(sem job runner/scheduler). Quando isso entrar:

1. As tabelas já têm os parâmetros necessários (`pid_kp`/`ki`/`kd` em
   `BrewSessionStep`, condição/ação em `AutomationRule`).
2. O motor consumiria essas tabelas como configuração, sem precisar
   de migration nova.

## Dependência de `feature_device_manager`

Sempre migrar/ativar `device_manager` antes — `mash_control` declara
isso em `feature.json` (`requires: ["feature_device_manager"]`).
