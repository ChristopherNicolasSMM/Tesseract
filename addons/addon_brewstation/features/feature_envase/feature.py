"""
addons/addon_brewstation/features/feature_envase/feature.py
"""
__module__ = "FeatureEnvase"

from core.feature_base import FeatureBase


class FeatureEnvase(FeatureBase):
    def register_models(self) -> list:
        from addons.addon_brewstation.features.feature_envase.model.envase import Envase
        from addons.addon_brewstation.features.feature_envase.model.item_envase import ItemEnvase

        return [Envase, ItemEnvase]

    def register_routes(self, app) -> None:
        names = ["envases", "item_envases"]
        base_controller = "addons.addon_brewstation.features.feature_envase.controller"
        base_routes = "addons.addon_brewstation.features.feature_envase.api.routes"

        import importlib
        for name in names:
            controller_mod = importlib.import_module(f"{base_controller}.{name}")
            routes_mod = importlib.import_module(f"{base_routes}.{name}_routes")
            app.register_blueprint(getattr(controller_mod, f"{name}_bp"))
            app.register_blueprint(getattr(routes_mod, f"{name}_api_bp"))

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_GROUP_ENVASE",
                "label": "Envase",
                "parent_code": "TX_GROUP_BREWSTATION",  # skill 10 secao 7.1 - agrupa sob o Addon pai
                "route": None,
                "icon": "bi-box2",
            },
            {
                "code": "TX_ENVASES",
                "label": "Envases",
                "parent_code": "TX_GROUP_ENVASE",
                "description": "Registro de empacotamento de um Lote.",
                "icon": "bi-box2-fill",
                "route": "/brewstation/envases",
                "permission_required": "envases.list",
            },
            {
                "code": "TX_ITEM_ENVASES",
                "label": "Itens de Envase",
                "parent_code": "TX_GROUP_ENVASE",
                "description": "Materiais de embalagem usados em um Envase.",
                "icon": "bi-list-check",
                "route": "/brewstation/item-envases",
                "permission_required": "item_envases.list",
            },
        ]
