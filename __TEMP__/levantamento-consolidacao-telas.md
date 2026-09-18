# Levantamento — Consolidação de Telas (estilo SAP) em todos os Addons

> Status: **[ABERTO]** — levantamento completo, nada implementado.
> Premissa confirmada com você: nenhuma transação existente é
> desativada — só ganham companhia de uma tela consolidada, com
> navegação melhor pra chegar nela.

## 1. Como a home/menu funciona hoje (achado, não é proposta)

`controller/core/pages.py` + `templates/core/home.html`: a home
renderiza, recursivamente, **toda** transação folha (`route`
preenchido) como um card, agrupada só pelos nós-pasta (`route=None`)
da árvore. Não existe hoje nenhuma distinção visual entre "tela de
fluxo consolidado" e "tela de detalhe/cadastro cru" — um card de
`Plant Workspace` aparece do mesmo tamanho e estilo que um card de
`Tanques`. Isso é o que faz uma tela ficar "perdida" no meio de 14
outras do mesmo Addon.

## 2. Proposta pontual pro "sistema de transação" (pequena, aditiva)

Um campo novo em `Transaction` (`model/core/transaction.py`):

```python
is_workspace = db.Column(db.Boolean, default=False, nullable=False)
```

- `home.html` passa a renderizar cards com `is_workspace=True` numa
  faixa própria, no topo da home, destacada (maior, com borda/cor de
  destaque, ícone diferenciado) — igual a um launchpad. As demais
  transações continuam exatamente onde estão hoje, sem nenhuma
  mudança de comportamento.
- Zero impacto em permissão, rota, menu lateral — é só um bit a mais
  pra decidir "esse card ganha destaque na home ou não". Nenhuma
  transação existente muda de `is_active`, `parent_id` ou rota.
- Continua sendo exatamente o padrão SAP que você descreveu: a tela
  consolidada é o "atalho rápido" (equivalente a digitar `ME52N` na
  barra de transação), as telas individuais continuam ali, servindo
  de relatório/detalhamento, sem sumir do menu lateral.

Isso é tudo que "o sistema de transação" precisa ganhar — o resto é
construir as telas consolidadas em si (seção 3) e marcar a transação
delas com `is_workspace=True`.

## 3. Inventário de candidatos, por Addon

### `addon_estoque` — maior candidato, e o único addon 100% flat

Hoje: **14 transações, todas soltas dentro de um único grupo**
(`TX_GROUP_ESTOQUE`, sem subgrupo nenhum) — ao contrário do
`feature_mash_control`, que já tem subgrupos (Receitas, Planta&Sessão,
Automação) desde a última reorganização de menu.

| Cluster (equivalente SAP) | Telas hoje soltas | Workspace proposto |
|---|---|---|
| **Compra (Procure-to-Pay)** — equivalente a ME5A/ME21N/MIGO | `Cotações` (Processo), `Pedidos de Compra`, `Movimentações` (recebimento) — 3 telas de topo + `Cotacao`/`ItemCotacao`/`ItemProcessoCotacao`/`ItemPedidoCompra` já embutidas nas grids (você já confirmou) | Um workspace por Processo de Cotação: abas RFQ → Cotações recebidas → Pedido gerado → Recebimentos — a linha do tempo completa de uma compra numa tela só |
| **Cadastro de Material** — equivalente a MM01/MM02 | `Materiais`, `Unidades de Material`, `Categorias`, `Tipos de Produto`, `Fabricantes`, `Origens`, `Composições` — 7 telas | Um workspace de Material com abas (Dados Básicos, Unidades, Classificação, Composição/BOM) — as 7 telas continuam existindo pra quem só quer mexer num cadastro auxiliar isolado |
| **Parceiro de Negócio** — equivalente a BP/XK01 | `Fornecedores`, `Transportadoras`, `Endereços` — 3 telas (`FornecedorEndereco`/`TransportadoraEndereco` já são achados como linha, não tela própria) | Um workspace de Parceiro com abas (Dados, Endereços por tipo) |
| Fora de cluster | `Saldo de Estoque` (é relatório, já é o formato certo) | — não mexe |

### `addon_brewstation` / `feature_mash_control` — já parcialmente feito

Plant Workspace já cobre Planta/Sessão/Receita(picker)/Automação/
Dashboard. Fora disso, ainda soltos (e intencionalmente **não**
absorvidos até agora, por decisão registrada no código):

| Cluster | Telas soltas | Observação |
|---|---|---|
| **Receita, detalhamento** | `Ingredientes de Receita`, `Etapas de Fermentação`, `Perfis de Água`, `Histórico de Receitas`, `De-Para de Ingredientes` — 5 telas | A aba "Receita" do Workspace hoje só faz o *picker* (`_tab_recipe_picker.html`) — não mostra ingredientes/fermentação/água juntos. Candidato natural a virar a aba Receita "cheia", com sub-abas |

### `feature_yeast_bank` — já tem um painel, mas não é workspace de verdade

7 telas (`yeast_bank_items`, `yeast_bank_events`,
`yeast_cell_count_histories`, `yeast_containers`,
`yeast_storage_devices`, `yeast_strains`, `yeast_bank_configs`) — hoje
tem um **painel** que já dá atalho pras 7, mas não junta dado (é hub
de links, não workspace com abas mostrando tudo junto). Candidato a
virar workspace de verdade por `YeastBankItem` (aba Eventos, aba
Contagens, aba Cepa/Container/Dispositivo).

### `addon_device_manager` — menor, mas claro

4 telas (`device_metadatas`, `device_actors`, `device_functions`,
`emulated_devices`). `DeviceMetadata` → `DeviceActor` já é
master-detail natural (um device, várias portas). Candidato a
workspace de Device com a lista de portas embutida.

### `feature_envase` — já em andamento (proposta anterior)

`Envases` + `Itens de Envase` + a precificação nova (proposta já
enviada) — esse já está sendo desenhado, não precisa de item novo
aqui.

### Sem candidato claro (poucas telas, já enxuto)

`feature_brew_father` (1 tela), `feature_ingredientes` (3 telas, cada
uma já é uma view tipada de `Material`, natureza diferente de
workflow).

## 4. Ordem sugerida (pra você decidir, não é decisão minha)

1. `addon_estoque` — Compra (maior volume de telas, fluxo mais
   parecido com o que você descreveu do SAP, e você já confirmou que
   parte da consolidação de dado já existe, falta só a tela)
2. `addon_estoque` — Cadastro de Material
3. `feature_mash_control` — Receita completa na aba existente
4. `feature_yeast_bank` — painel vira workspace de verdade
5. `addon_device_manager` — Device + portas
6. `addon_estoque` — Parceiro de Negócio

## Próximos passos

1. Você aplica o patch de select box e confirma.
2. Você decide se a proposta do campo `is_workspace` (seção 2) serve
   como está, ou quer outra forma de destaque na home.
3. Você escolhe por onde começar (ordem da seção 4, ou outra) —
   sigo o mesmo ritmo de sempre: uma frente de trabalho por vez.
