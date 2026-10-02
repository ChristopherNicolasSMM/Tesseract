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

## Registrar envase na sessão da planta

Abra o lote na aba Sessões, inclusive se ele for antigo. Em Preparar envase,
selecione o produto, informe os litros e, se desejar, data e tipo do envase.
Consulte a prévia e confira componentes, unidades, custos e avisos.

Clique em **Registrar envase deste lote**. O modal informa se também serão
consumidos ingredientes ainda não confirmados. Cancelar o modal não grava
nada. Confirmar registra o envase e as baixas de estoque na mesma operação,
retornando à sessão escolhida. Ingredientes já confirmados e seu custo
registrado são preservados. Pendências precisam ser resolvidas primeiro.

Se a resposta se perder, tente novamente com a mesma confirmação exibida.
Essa repetição recupera o mesmo envase, sem outra baixa. Consultar uma nova
prévia inicia outro registro e permite um envase adicional. A prévia não
reserva estoque: composição e custos são conferidos no registro.

Para estornar, use o detalhe de envase existente. A integração do estorno
dentro da sessão e a consolidação da precificação são próximas etapas.


### Continuidade de envase no lote

Na aba Sessões do workspace, o registro de envase (2A.2) agora é acompanhado
por detalhes e estorno (2B). A abertura dos detalhes é somente leitura e usa
custos/saídas registrados. O estorno exige motivo e confirmação, devolve
embalagens pelo estoque central e preserva ingredientes/custo do lote.
A precificação continua em sua tela própria e seu alinhamento aos snapshots
permanece uma etapa posterior.
