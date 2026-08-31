"""
addons/addon_estoque/addon.py

Addon novo, independente - gestao generica de materiais estocaveis
(materia-prima, embalagem, kit/composicao) com movimentacao e saldo.
Ver docs/skills/02-nomenclatura-tabelas-e-prefixos.md e
addons/addon_estoque/docs/technical/ para o desenho completo.
"""
__module__ = "AddonEstoque"

from core.addon_base import AddonBase


class AddonEstoque(AddonBase):
    def register_models(self) -> list:
        from addons.addon_estoque.root.model.material import Material
        from addons.addon_estoque.root.model.composicao import Composicao
        from addons.addon_estoque.root.model.movimentacao import Movimentacao
        from addons.addon_estoque.root.model.saldo import Saldo
        from addons.addon_estoque.root.model.fabricante import Fabricante
        from addons.addon_estoque.root.model.origem import Origem
        from addons.addon_estoque.root.model.tipo_produto import TipoProduto
        from addons.addon_estoque.root.model.categoria import Categoria
        from addons.addon_estoque.root.model.material_unidade import MaterialUnidade
        from addons.addon_estoque.root.model.fornecedor import Fornecedor
        from addons.addon_estoque.root.model.transportadora import Transportadora
        from addons.addon_estoque.root.model.endereco import Endereco
        from addons.addon_estoque.root.model.fornecedor_endereco import FornecedorEndereco
        from addons.addon_estoque.root.model.transportadora_endereco import TransportadoraEndereco
        from addons.addon_estoque.root.model.pedido_compra import PedidoCompra
        from addons.addon_estoque.root.model.item_pedido_compra import ItemPedidoCompra
        from addons.addon_estoque.root.model.processo_cotacao import ProcessoCotacao
        from addons.addon_estoque.root.model.cotacao import Cotacao
        from addons.addon_estoque.root.model.item_cotacao import ItemCotacao
        from addons.addon_estoque.root.model.item_processo_cotacao import ItemProcessoCotacao

        # Lookups (Fabricante/Origem/TipoProduto/Categoria) primeiro só
        # por legibilidade - create_all resolve ordem de FK via
        # metadata do SQLAlchemy, não pela ordem desta lista.
        # MaterialUnidade depende de Material (FK) - skill 23, Fase 2.
        # Fase 3 (skill 23): Fornecedor/Transportadora primeiro (dono),
        # Endereco (dado puro), depois os vínculos (dependem dos 3).
        # Fase 4 (skill 23): PedidoCompra/ItemPedidoCompra por último
        # (dependem de Fornecedor/Transportadora/MaterialUnidade); Movimentacao
        # ja tem FK opcional para ItemPedidoCompra (rastro de compra).
        # Fase 6.1 (skill 24): ProcessoCotacao -> Cotacao -> ItemCotacao,
        # mesma cadeia de dependencia de PedidoCompra/ItemPedidoCompra.
        # ItemProcessoCotacao (correcao pos-Fase 6.3): o item pedido
        # vive no processo, ItemCotacao so responde preco pra ele.
        return [
            Fabricante, Origem, TipoProduto, Categoria, Material, Composicao, Movimentacao, Saldo,
            MaterialUnidade, Fornecedor, Transportadora, Endereco, FornecedorEndereco, TransportadoraEndereco,
            PedidoCompra, ItemPedidoCompra, ProcessoCotacao, ItemProcessoCotacao, Cotacao, ItemCotacao,
        ]

    def register_routes(self, app) -> None:
        from addons.addon_estoque.root.controller.materials import materials_bp
        from addons.addon_estoque.root.api.routes.materials_routes import materials_api_bp
        from addons.addon_estoque.root.controller.composicaos import composicaos_bp
        from addons.addon_estoque.root.api.routes.composicaos_routes import composicaos_api_bp
        from addons.addon_estoque.root.controller.movimentacaos import movimentacaos_bp
        from addons.addon_estoque.root.api.routes.movimentacaos_routes import movimentacaos_api_bp
        from addons.addon_estoque.root.controller.saldos import saldos_bp
        from addons.addon_estoque.root.api.routes.saldos_routes import saldos_api_bp
        from addons.addon_estoque.root.controller.fabricantes import fabricantes_bp
        from addons.addon_estoque.root.api.routes.fabricantes_routes import fabricantes_api_bp
        from addons.addon_estoque.root.controller.origems import origems_bp
        from addons.addon_estoque.root.api.routes.origems_routes import origems_api_bp
        from addons.addon_estoque.root.controller.tipo_produtos import tipo_produtos_bp
        from addons.addon_estoque.root.api.routes.tipo_produtos_routes import tipo_produtos_api_bp
        from addons.addon_estoque.root.controller.categorias import categorias_bp
        from addons.addon_estoque.root.api.routes.categorias_routes import categorias_api_bp
        from addons.addon_estoque.root.controller.material_unidades import material_unidades_bp
        from addons.addon_estoque.root.api.routes.material_unidades_routes import material_unidades_api_bp
        from addons.addon_estoque.root.controller.fornecedores import fornecedores_bp
        from addons.addon_estoque.root.api.routes.fornecedores_routes import fornecedores_api_bp
        from addons.addon_estoque.root.controller.transportadoras import transportadoras_bp
        from addons.addon_estoque.root.api.routes.transportadoras_routes import transportadoras_api_bp
        from addons.addon_estoque.root.controller.enderecos import enderecos_bp
        from addons.addon_estoque.root.api.routes.enderecos_routes import enderecos_api_bp
        # Fase 5 (skill 23): FornecedorEndereco/TransportadoraEndereco/
        # ItemPedidoCompra não têm mais tela própria — o controller de
        # UI (list/manage/detail) e os templates foram removidos. A API
        # REST continua existindo e registrada normalmente (consumida
        # pelas telas desenhadas de Fornecedor/Transportadora/Pedido de
        # Compra, ver static/js/estoque/).
        from addons.addon_estoque.root.api.routes.fornecedor_enderecos_routes import fornecedor_enderecos_api_bp
        from addons.addon_estoque.root.api.routes.transportadora_enderecos_routes import transportadora_enderecos_api_bp
        from addons.addon_estoque.root.controller.pedido_compras import pedido_compras_bp
        from addons.addon_estoque.root.api.routes.pedido_compras_routes import pedido_compras_api_bp
        from addons.addon_estoque.root.api.routes.item_pedido_compras_routes import item_pedido_compras_api_bp
        from addons.addon_estoque.root.controller.processo_cotacaos import processo_cotacaos_bp
        from addons.addon_estoque.root.api.routes.processo_cotacaos_routes import processo_cotacaos_api_bp
        # Fase 6.1 (skill 24): Cotacao/ItemCotacao já nascem sem tela
        # própria (mesma decisão da Fase 5) — só API.
        from addons.addon_estoque.root.api.routes.cotacaos_routes import cotacaos_api_bp
        from addons.addon_estoque.root.api.routes.item_cotacaos_routes import item_cotacaos_api_bp
        from addons.addon_estoque.root.api.routes.item_processo_cotacaos_routes import item_processo_cotacaos_api_bp

        # Fase 4 (skill 23): ação "receber" não é CRUD genérico, então
        # não é gerada pelo CrudGen — anexada aqui ao blueprint já
        # pronto (ver nota em controller/pedido_compras_hooks.py sobre
        # por que isso não pode ficar dentro do próprio hooks.py).
        # GUARDA (achado real, ver BACKLOG): pedido_compras_bp é objeto
        # de módulo, reaproveitado entre múltiplos create_app() no
        # mesmo processo (ex.: suíte de testes) — add_url_rule só pode
        # rodar uma vez; sem a guarda, o 2º create_app() do processo
        # levanta AssertionError do Flask ("blueprint already
        # registered").
        if not getattr(pedido_compras_bp, "_receber_route_registered", False):
            from addons.addon_estoque.root.controller.pedido_compras_hooks import receber_view
            pedido_compras_bp.add_url_rule(
                "/<int:id>/receber", endpoint="receber", view_func=receber_view, methods=["POST"],
            )
            pedido_compras_bp._receber_route_registered = True

        # Entrada de Mercadoria (correção — achado do Christopher):
        # endpoint JSON novo, mesmo padrão de guarda.
        if not getattr(pedido_compras_bp, "_entrada_mercadoria_route_registered", False):
            from addons.addon_estoque.root.controller.pedido_compras_hooks import entrada_mercadoria_view
            pedido_compras_bp.add_url_rule(
                "/<int:id>/entrada-mercadoria", endpoint="entrada_mercadoria",
                view_func=entrada_mercadoria_view, methods=["POST"],
            )
            pedido_compras_bp._entrada_mercadoria_route_registered = True

        # Ações em massa (achado do Christopher — seleção de linhas na
        # lista de Materiais): 4 endpoints JSON novos, mesmo padrão de
        # guarda contra dupla execução.
        if not getattr(materials_bp, "_acoes_em_massa_registradas", False):
            from addons.addon_estoque.root.controller.materials_hooks import (
                movimentar_em_massa_view, criar_cotacao_em_massa_view,
                criar_pedido_em_massa_view, modificar_em_massa_view,
            )
            materials_bp.add_url_rule(
                "/acoes-em-massa/movimentar", endpoint="movimentar_em_massa",
                view_func=movimentar_em_massa_view, methods=["POST"],
            )
            materials_bp.add_url_rule(
                "/acoes-em-massa/criar-cotacao", endpoint="criar_cotacao_em_massa",
                view_func=criar_cotacao_em_massa_view, methods=["POST"],
            )
            materials_bp.add_url_rule(
                "/acoes-em-massa/criar-pedido", endpoint="criar_pedido_em_massa",
                view_func=criar_pedido_em_massa_view, methods=["POST"],
            )
            materials_bp.add_url_rule(
                "/acoes-em-massa/modificar", endpoint="modificar_em_massa",
                view_func=modificar_em_massa_view, methods=["POST"],
            )
            materials_bp._acoes_em_massa_registradas = True

        # Fase 6.2 (skill 24): ações "selecionar-vencedor"/
        # "desmarcar-vencedor" — mesmo padrão de guarda da ação
        # "receber" acima.
        if not getattr(item_cotacaos_api_bp, "_vencedor_routes_registered", False):
            from addons.addon_estoque.root.api.routes.item_cotacaos_routes_hooks import (
                selecionar_vencedor_view, desmarcar_vencedor_view,
            )
            item_cotacaos_api_bp.add_url_rule(
                "/<int:id>/selecionar-vencedor", endpoint="selecionar_vencedor",
                view_func=selecionar_vencedor_view, methods=["POST"],
            )
            item_cotacaos_api_bp.add_url_rule(
                "/<int:id>/desmarcar-vencedor", endpoint="desmarcar_vencedor",
                view_func=desmarcar_vencedor_view, methods=["POST"],
            )
            item_cotacaos_api_bp._vencedor_routes_registered = True

        # Fase 6.3 (skill 24): ação "gerar-pedido" — mesmo padrão de
        # guarda das ações acima.
        if not getattr(processo_cotacaos_bp, "_gerar_pedido_route_registered", False):
            from addons.addon_estoque.root.controller.processo_cotacaos_hooks import gerar_pedido_view
            processo_cotacaos_bp.add_url_rule(
                "/<int:id>/gerar-pedido", endpoint="gerar_pedido", view_func=gerar_pedido_view, methods=["POST"],
            )
            processo_cotacaos_bp._gerar_pedido_route_registered = True

        for bp in [
            materials_bp, materials_api_bp,
            composicaos_bp, composicaos_api_bp,
            movimentacaos_bp, movimentacaos_api_bp,
            saldos_bp, saldos_api_bp,
            fabricantes_bp, fabricantes_api_bp,
            origems_bp, origems_api_bp,
            tipo_produtos_bp, tipo_produtos_api_bp,
            categorias_bp, categorias_api_bp,
            material_unidades_bp, material_unidades_api_bp,
            fornecedores_bp, fornecedores_api_bp,
            transportadoras_bp, transportadoras_api_bp,
            enderecos_bp, enderecos_api_bp,
            fornecedor_enderecos_api_bp,
            transportadora_enderecos_api_bp,
            pedido_compras_bp, pedido_compras_api_bp,
            item_pedido_compras_api_bp,
            processo_cotacaos_bp, processo_cotacaos_api_bp,
            cotacaos_api_bp,
            item_cotacaos_api_bp,
            item_processo_cotacaos_api_bp,
        ]:
            app.register_blueprint(bp)

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_GROUP_ESTOQUE",
                "label": "Estoque",
                "parent_code": None,
                "route": None,
                "icon": "bi-box-seam",
            },
            {
                "code": "TX_MATERIALS",
                "label": "Materiais",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Cadastro de itens estocáveis.",
                "icon": "bi-box",
                "route": "/estoque/materials",
                "permission_required": "materials.list",
            },
            {
                "code": "TX_MOVIMENTACAOS",
                "label": "Movimentações",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Ledger de entrada/saída/ajuste de estoque.",
                "icon": "bi-arrow-left-right",
                "route": "/estoque/movimentacaos",
                "permission_required": "movimentacaos.list",
            },
            {
                "code": "TX_SALDOS",
                "label": "Saldo de Estoque",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Saldo atual por material.",
                "icon": "bi-clipboard-data",
                "route": "/estoque/saldos",
                "permission_required": "saldos.list",
            },
            {
                "code": "TX_COMPOSICAOS",
                "label": "Composições",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Materiais compostos por outros materiais (BOM/kit).",
                "icon": "bi-diagram-3",
                "route": "/estoque/composicaos",
                "permission_required": "composicaos.list",
            },
            {
                "code": "TX_FABRICANTES",
                "label": "Fabricantes",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Cadastro de fabricantes/marcas de materiais.",
                "icon": "bi-building",
                "route": "/estoque/fabricantes",
                "permission_required": "fabricantes.list",
            },
            {
                "code": "TX_ORIGEMS",
                "label": "Origens",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Cadastro de origens de material (nacional/importado/etc.).",
                "icon": "bi-globe",
                "route": "/estoque/origems",
                "permission_required": "origems.list",
            },
            {
                "code": "TX_TIPO_PRODUTOS",
                "label": "Tipos de Produto",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Classificação de materiais (insumo, embalagem, etc.).",
                "icon": "bi-tags",
                "route": "/estoque/tipo-produtos",
                "permission_required": "tipo_produtos.list",
            },
            {
                "code": "TX_CATEGORIAS",
                "label": "Categorias",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Categorias de material (substitui o antigo campo livre).",
                "icon": "bi-bookmark",
                "route": "/estoque/categorias",
                "permission_required": "categorias.list",
            },
            {
                "code": "TX_MATERIAL_UNIDADES",
                "label": "Unidades de Material",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Unidades de compra/consumo por material, com fator de conversão para a unidade-base (skill 23, Fase 2).",
                "icon": "bi-rulers",
                "route": "/estoque/material-unidades",
                "permission_required": "material_unidades.list",
            },
            {
                "code": "TX_FORNECEDORES",
                "label": "Fornecedores",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Cadastro de fornecedores (skill 23, Fase 3).",
                "icon": "bi-truck",
                "route": "/estoque/fornecedores",
                "permission_required": "fornecedores.list",
            },
            {
                "code": "TX_TRANSPORTADORAS",
                "label": "Transportadoras",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Cadastro de transportadoras (skill 23, Fase 3).",
                "icon": "bi-truck-flatbed",
                "route": "/estoque/transportadoras",
                "permission_required": "transportadoras.list",
            },
            {
                "code": "TX_ENDERECOS",
                "label": "Endereços",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Endereços reutilizáveis, vinculados a Fornecedor/Transportadora (skill 23, Fase 3).",
                "icon": "bi-geo-alt",
                "route": "/estoque/enderecos",
                "permission_required": "enderecos.list",
            },
            # TX_FORNECEDOR_ENDERECOS / TX_TRANSPORTADORA_ENDERECOS
            # removidas (skill 23, Fase 5) — vínculo agora aparece
            # embutido no detalhe de Fornecedor/Transportadora, sem
            # tela/transação própria. API continua ativa.
            {
                "code": "TX_PEDIDO_COMPRAS",
                "label": "Pedidos de Compra",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Sistema de compras: pedido -> recebimento -> movimentação de entrada automática (skill 23, Fase 4/5).",
                "icon": "bi-cart-check",
                "route": "/estoque/pedido-compras",
                "permission_required": "pedido_compras.list",
            },
            # TX_ITEM_PEDIDO_COMPRAS removida (skill 23, Fase 5) — itens
            # aparecem na aba "Itens" do detalhe de Pedido de Compra.
            {
                "code": "TX_PROCESSO_COTACAOS",
                "label": "Cotações",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Processo de cotação (RFQ): convida fornecedores, compara preço por Material, gera Pedido de Compra do vencedor (skill 24, Fase 6.1).",
                "icon": "bi-clipboard-data",
                "route": "/estoque/processo-cotacaos",
                "permission_required": "processo_cotacaos.list",
            },
            # TX_COTACAOS / TX_ITEM_COTACAOS não existem (skill 24) —
            # Cotacao/ItemCotacao não têm tela própria desde o início,
            # mesma decisão da Fase 5 para os vínculos de Endereço.
        ]
