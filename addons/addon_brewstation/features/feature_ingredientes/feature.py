"""
addons/addon_brewstation/features/feature_ingredientes/feature.py
"""
__module__ = "FeatureIngredientes"

from core.feature_base import FeatureBase


class FeatureIngredientes(FeatureBase):
    def register_models(self) -> list:
        from addons.addon_brewstation.features.feature_ingredientes.model.malte import Malte
        from addons.addon_brewstation.features.feature_ingredientes.model.lupulo import Lupulo
        from addons.addon_brewstation.features.feature_ingredientes.model.levedura import Levedura

        return [Malte, Lupulo, Levedura]

    def register_routes(self, app) -> None:
        names = ["maltes", "lupulos", "leveduras"]
        base_controller = "addons.addon_brewstation.features.feature_ingredientes.controller"
        base_routes = "addons.addon_brewstation.features.feature_ingredientes.api.routes"

        import importlib
        for name in names:
            controller_mod = importlib.import_module(f"{base_controller}.{name}")
            routes_mod = importlib.import_module(f"{base_routes}.{name}_routes")
            app.register_blueprint(getattr(controller_mod, f"{name}_bp"))
            app.register_blueprint(getattr(routes_mod, f"{name}_api_bp"))

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_GROUP_INGREDIENTES",
                "label": "Ingredientes",
                "parent_code": "TX_GROUP_BREWSTATION",  # skill 10 secao 7.1 - agrupa sob o Addon pai
                "route": None,
                "icon": "bi-basket2",
            },
            {
                "code": "TX_MALTES",
                "label": "Maltes",
                "parent_code": "TX_GROUP_INGREDIENTES",
                "description": "Especificações de malte, complementares ao Material do estoque.",
                "icon": "bi-grain",
                "route": "/brewstation/maltes",
                "permission_required": "maltes.list",
            },
            {
                "code": "TX_LUPULOS",
                "label": "Lúpulos",
                "parent_code": "TX_GROUP_INGREDIENTES",
                "description": "Especificações de lúpulo, complementares ao Material do estoque.",
                "icon": "bi-flower1",
                "route": "/brewstation/lupulos",
                "permission_required": "lupulos.list",
            },
            {
                "code": "TX_LEVEDURAS",
                "label": "Leveduras",
                "parent_code": "TX_GROUP_INGREDIENTES",
                "description": "Especificações de levedura para cálculo de receita.",
                "icon": "bi-moisture",
                "route": "/brewstation/leveduras",
                "permission_required": "leveduras.list",
            },
        ]
