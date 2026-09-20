# 01 — Visão Geral (Addon Estoque)

> **Atualizado nesta sessão** (auditoria de documentação — este addon
> cresceu por 3 rodadas reais de arquitetura, skills 23/24/25, sem que
> `docs/technical/` acompanhasse). Reflete o código real hoje: taxonomia
> completa, fornecedores/transportadoras, compras, cotação (RFQ) e
> ações em massa.

## Propósito

Gestão de materiais estocáveis — matéria-prima, embalagem,
kits/composições — com ledger de movimentação, saldo materializado,
e o ciclo de compra completo que alimenta esse ledger: taxonomia de
classificação, cadastro de fornecedores/transportadoras, Pedido de
Compra, Cotação de Fornecedores (RFQ) e Entrada de Mercadoria. Não
conhece nenhum domínio de negócio específico de cervejaria — existe
para ser dependência de qualquer Addon que precise de controle de
estoque ou de comprar algo, sem reescrever a mesma lógica.

## Dependências

Nenhuma (`requires: []`) — é infraestrutura de base.

## O que expõe (`provides`)

- `material_data` — identidade e atributos de Material
- `stock_movement_data` — ledger de movimentações
- `stock_balance_data` — saldo atual por Material

Consumido por outros Addons **só via service público** (nunca FK
direta — skill 02). `addon_brewstation` é o consumidor real hoje
(`feature_mash_control` para resolução de ingredientes,
`feature_ingredientes`, `feature_envase`) — todos via
`material_lookup.get_material()`/`buscar_material_por_termo()`.

## Blocos do addon (visão de alto nível)

| Bloco | Entidades | Papel |
|---|---|---|
| **Taxonomia** | `Fabricante`, `Origem`, `TipoProduto`, `Categoria` | Classificação de `Material` — `TipoProduto` é o eixo de natureza (Insumo/Embalagem/Produto Acabado/Peça/Uso e Consumo), `Categoria` é a classificação fina dentro de um `TipoProduto` |
| **Cadastro base** | `Material`, `MaterialUnidade`, `Composicao` | Identidade de tudo que pode ser estocado, com múltiplas unidades de medida (compra × consumo, com fator de conversão) e relação pai/componente (BOM) |
| **Parceiros** | `Fornecedor`, `Transportadora`, `Endereco`, `FornecedorEndereco`, `TransportadoraEndereco` | Quem fornece e quem transporta, com endereços reutilizáveis (1:N por dono, sem padrão polimórfico) |
| **Compra** | `PedidoCompra`, `ItemPedidoCompra` | Máquina de estado rascunho→enviado→confirmado→recebido; receber gera `Movimentacao` automaticamente |
| **Cotação (RFQ)** | `ProcessoCotacao`, `Cotacao`, `ItemProcessoCotacao`, `ItemCotacao` | Comparação de preço entre fornecedores antes de fechar um `PedidoCompra`; "Gerar Pedido" converte vencedores em pedido |
| **Ledger** | `Movimentacao`, `Saldo` | Registro imutável de entrada/saída/ajuste + cache materializado do saldo atual |

Ver `03-fluxos.md` para como esses blocos se encadeiam na prática, e
`04-modelo-de-dados.md` para o schema completo das 15 tabelas.

## Ações em massa (achado real, ver `03-fluxos.md`)

A lista de Materiais permite selecionar várias linhas e disparar, de
uma vez: Movimentar Estoque, Criar Cotação, Criar Pedido, ou
Modificação em Massa (campos de classificação). Todas passam pelos
mesmos services que o fluxo unitário usa — nenhuma lógica duplicada.

## Sobre "aprovação" no fluxo de compra

**Não existe uma permissão ou papel de "aprovador" separado hoje.**
A transição de status de `PedidoCompra` (`rascunho`→`enviado`→
`confirmado`) é feita por qualquer usuário com a permissão padrão
`pedido_compras.update` — o "confirmado" funciona, na prática, como o
portão antes do recebimento (só a partir dele
`estoque_service.receber_pedido_compra()` aceita rodar), mas não há
uma segunda assinatura, papel específico, ou registro de quem
aprovou além do `updated_at`/log padrão. Se um fluxo de aprovação
formal (papel dedicado, exigência de dois usuários diferentes, etc.)
for necessário, é uma decisão de arquitetura nova — não confundir a
nomenclatura de status (`confirmado`) com um mecanismo de aprovação
que ainda não existe.

## Origem

Nasceu da análise do módulo legado `plugin_integ_bFather` (BrewStation
antigo, pré-Tesseract) — o bloco de `Embalagem`/`TipoEmbalagem`/estoque
de ingredientes daquele módulo não seguia a convenção do Tesseract
(criava tabela apesar de se chamar "plugin" — skill 00 proíbe isso) e
foi redesenhado do zero como este Addon. A ampliação para taxonomia
completa, fornecedores, compras e RFQ veio de três sessões de
arquitetura dedicadas (skills 23, 24, 25) depois que o desenho
original (só Material/Composição/Movimentação/Saldo) se mostrou
insuficiente para o uso real da cervejaria.

## Documentos técnicos relacionados

`02-diagrama-c4.md`, `03-fluxos.md`, `04-modelo-de-dados.md`,
`05-casos-de-uso.md`, `06-manutencao-e-expansao.md`.

## Pendências conhecidas

- Recebimento **sempre total** — recebimento parcial de um
  `PedidoCompra` fica para quando o volume real de uso justificar
  (decisão explícita, registrada na skill 23).
- Regra de bloqueio (ou não) de saída sem saldo suficiente — em
  aberto; hoje o sistema alerta mas não bloqueia.
- `i18n/pt_BR.json` — ainda não escrito (gap conhecido, registrado em
  `BACKLOG.md`, não específico deste Addon).
- Fluxo de aprovação formal de `PedidoCompra` — não existe, ver seção
  acima.
- Domínio de Cálculo/precificação (base de custo, base dedutiva,
  impostos cadastrados) que também vai consumir este Addon — parked,
  sessão dedicada futura.
