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

        # Lookups (Fabricante/Origem/TipoProduto/Categoria) primeiro só
        # por legibilidade - create_all resolve ordem de FK via
        # metadata do SQLAlchemy, não pela ordem desta lista.
        return [Fabricante, Origem, TipoProduto, Categoria, Material, Composicao, Movimentacao, Saldo]

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

        for bp in [
            materials_bp, materials_api_bp,
            composicaos_bp, composicaos_api_bp,
            movimentacaos_bp, movimentacaos_api_bp,
            saldos_bp, saldos_api_bp,
            fabricantes_bp, fabricantes_api_bp,
            origems_bp, origems_api_bp,
            tipo_produtos_bp, tipo_produtos_api_bp,
            categorias_bp, categorias_api_bp,
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
        ]
