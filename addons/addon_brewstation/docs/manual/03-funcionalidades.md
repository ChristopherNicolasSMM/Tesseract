# 03 — Funcionalidades (BrewStation)

Ver o manual de cada área:
- **Banco de Levedura** — `features/feature_yeast_bank/docs/manual/03-funcionalidades.md`
- **Controle de Mostura (Receitas, Sessões, Automação)** — `features/feature_mash_control/docs/manual/03-funcionalidades.md`
- **Ingredientes** — `features/feature_ingredientes/docs/manual/03-funcionalidades.md`
- **Envase** — `features/feature_envase/docs/manual/03-funcionalidades.md`
- **Integração BrewFather** — `features/feature_brew_father/docs/manual/03-funcionalidades.md`

Dispositivos IoT (sensores/atuadores) e Estoque de materiais vivem em
áreas próprias do sistema — não são parte do BrewStation, mas são
usados por ele.

## Seletores e aproveitamento da tela de mostura

Na aba Sessões, a lista e o resumo ficam na primeira linha. Os demais cards
ocupam a largura abaixo, incluindo ingredientes e preparação de envase.
Em uma janela estreita, os cards são empilhados.

Para escolher planta, tanque, painel, sessão, material ou função de dispositivo,
digite parte do nome e clique no resultado. Somente digitar não confirma a
escolha. Para remover uma referência opcional, apague o texto. No Dashboard,
o botão **Detecção automática** volta à sessão escolhida automaticamente.
Os seletores de tanques respeitam a planta e a tubulação oferece funções de
atuadores. Status, tipos e demais opções fixas continuam nas caixas de seleção.
As opções pesquisadas devem ser legíveis nos temas claro e escuro.
