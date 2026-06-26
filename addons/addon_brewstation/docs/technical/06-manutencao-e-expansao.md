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

Ver `features/feature_mash_control/docs/technical/06-manutencao-e-expansao.md`
— os parâmetros já existem nas tabelas (`pid_kp`/`ki`/`kd`,
`AutomationRule`), só falta o motor que os consome continuamente.
