# 06 — Manutenção e Expansão (Feature Mash Control)

## Sobre o motor de controle em tempo real (parcialmente portado)

O BrewStation original tinha PID controller, motor de automação
(avalia sensor continuamente) e scheduler de processo. Do que já foi
portado para o Tesseract:

- **Motor de automação: portado e ativo.** `AutomationRule` avalia de
  fato via EventBus do Core (`device_manager.actor.value_changed`) —
  é 100% orientado a evento, sem polling/scheduler, então não precisou
  esperar o sistema de Tasks. Ver `03-fluxos.md` e
  `docs/skills/05-proposta-addon-device-manager-e-mqtt.md`, Fase E.
- **Loop de controle PID contínuo: ainda não portado.** As tabelas já
  têm os parâmetros necessários (`pid_kp`/`ki`/`kd` em
  `BrewSessionStep`), mas não existe nenhum processo consumindo esses
  parâmetros continuamente ainda — diferente do motor de automação
  (evento pontual), um PID de verdade precisa rodar em intervalos
  regulares. Candidato natural: `services/core/task_service.py`
  (sistema de Tasks/`APScheduler`, já existe e já é usado por outras
  áreas do Core — `/admin/tasks/`), não vale mais a justificativa
  antiga de "não temos scheduler ainda".
2. Quando isso entrar, o motor consumiria as tabelas já existentes
   como configuração, sem precisar de migration nova.

## Dependência de `addon_device_manager`

Sempre ativar `device_manager` antes — `mash_control` declara isso em
`feature.json` (`"requires": ["device_manager", "estoque"]` — nome
correto do Addon promovido, skill 05; a Feature também depende de
`estoque` pra resolução de ingrediente de receita).
