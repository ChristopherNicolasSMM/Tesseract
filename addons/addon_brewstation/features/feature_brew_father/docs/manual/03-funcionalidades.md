# 03 — Funcionalidades (Integração BrewFather)

## Sincronizar Receitas

Busca as receitas da sua conta BrewFather e traz pro sistema —
ingredientes, etapas de mostura e fermentação. Pode ser clicado várias
vezes; receitas já importadas não são duplicadas.

## Sincronizações (histórico)

Lista de cada sincronização já feita — quando rodou, quantas receitas
processou, e se deu algum erro.

## Resolver Ingredientes Pendentes (De-Para)

Tela que aparece quando existem ingredientes importados que ainda não
foram ligados a um Material do Estoque. Duas formas de resolver cada
um:
- **Buscar Material existente**: digite o nome no campo de busca e
  escolha na lista.
- **Cadastrar Material novo**: digite um nome novo — o sistema cria o
  Material automaticamente (com dados básicos, que podem ser
  completados depois na tela de Materiais).

## Cadastrar todos automaticamente

Atalho pra quem não quer resolver ingrediente por ingrediente —
cadastra um Material novo pra cada ingrediente ainda pendente, de uma
vez só. Os materiais criados assim ficam marcados como "pendente de
revisão" no Estoque (ver manual do Estoque).
