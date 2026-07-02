# 03 — Fluxos (Feature Brew Father)

Fluxo completo (parse da API + resolução de ingrediente) documentado
em `features/feature_mash_control/docs/technical/03-fluxos.md`
("Sequência: importação de receita + resolução de ingrediente") — não
duplicado aqui pra evitar dessincronia entre os dois documentos.

Responsabilidade exclusiva desta Feature: consultar a API BrewFather e
converter o payload pro formato de entrada que
`ingredient_resolution_service` espera (descrição + quantidade +
unidade por ingrediente).
