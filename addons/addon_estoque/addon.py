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

        # Lookups (Fabricante/Origem/TipoProduto/Categoria) primeiro só
        # por legibilidade - create_all resolve ordem de FK via
        # metadata do SQLAlchemy, não pela ordem desta lista.
        # MaterialUnidade depende de Material (FK) - skill 23, Fase 2.
        # Fase 3 (skill 23): Fornecedor/Transportadora primeiro (dono),
        # Endereco (dado puro), depois os vínculos (dependem dos 3).
        return [
            Fabricante, Origem, TipoProduto, Categoria, Material, Composicao, Movimentacao, Saldo,
            MaterialUnidade, Fornecedor, Transportadora, Endereco, FornecedorEndereco, TransportadoraEndereco,
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
        from addons.addon_estoque.root.controller.fornecedor_enderecos import fornecedor_enderecos_bp
        from addons.addon_estoque.root.api.routes.fornecedor_enderecos_routes import fornecedor_enderecos_api_bp
        from addons.addon_estoque.root.controller.transportadora_enderecos import transportadora_enderecos_bp
        from addons.addon_estoque.root.api.routes.transportadora_enderecos_routes import transportadora_enderecos_api_bp

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
            fornecedor_enderecos_bp, fornecedor_enderecos_api_bp,
            transportadora_enderecos_bp, transportadora_enderecos_api_bp,
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
            {
                "code": "TX_FORNECEDOR_ENDERECOS",
                "label": "Endereços de Fornecedor",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Vínculo Fornecedor x Endereço, com tipo (cobrança/entrega/etc.) e principal.",
                "icon": "bi-geo",
                "route": "/estoque/fornecedor-enderecos",
                "permission_required": "fornecedor_enderecos.list",
            },
            {
                "code": "TX_TRANSPORTADORA_ENDERECOS",
                "label": "Endereços de Transportadora",
                "parent_code": "TX_GROUP_ESTOQUE",
                "description": "Vínculo Transportadora x Endereço, com tipo (cobrança/entrega/etc.) e principal.",
                "icon": "bi-geo",
                "route": "/estoque/transportadora-enderecos",
                "permission_required": "transportadora_enderecos.list",
            },
        ]
