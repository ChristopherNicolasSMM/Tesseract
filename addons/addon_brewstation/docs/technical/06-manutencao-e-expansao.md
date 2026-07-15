# 06 — Manutenção e Expansão (Addon BrewStation)

## Adicionar uma nova Feature

Ver `docs/technical/06-manutencao-e-expansao.md` (sistema), seção
"Como adicionar uma nova Feature a um Addon existente" — aplica-se
diretamente aqui.

## Sobre `integ_bfather`

Não migrado do BrewStation original — aguardando reescrita dedicada,
não uma simples portabilidade (a API do BrewFather mudou desde o
código original). Não cadastrar nenhum model novo com esse nome até a
reescrita ser decidida.

## Sobre o motor de controle em tempo real

O motor de **automação** (`AutomationRule` → `automation_engine.py`)
**já está implementado e ativo** — event-driven via EventBus do Core,
sem scheduler. O que falta é só o loop de **PID contínuo** (parâmetros
`pid_kp`/`ki`/`kd` já existem na tabela, sem processo consumindo).
Ver `features/feature_mash_control/docs/technical/06-manutencao-e-expansao.md`
pro detalhe e candidato de implementação (sistema de Tasks do Core).
