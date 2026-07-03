"""
addons/addon_brewstation/features/feature_brew_father/feature.py
"""
__module__ = "FeatureBrewFather"

from core.feature_base import FeatureBase


class FeatureBrewFather(FeatureBase):
    def register_models(self) -> list:
        from addons.addon_brewstation.features.feature_brew_father.model.brew_father_sync import BrewFatherSync

        return [BrewFatherSync]

    def register_routes(self, app) -> None:
        names = ["brewfather_syncs"]
        base_controller = "addons.addon_brewstation.features.feature_brew_father.controller"
        base_routes = "addons.addon_brewstation.features.feature_brew_father.api.routes"

        import importlib
        for name in names:
            controller_mod = importlib.import_module(f"{base_controller}.{name}")
            routes_mod = importlib.import_module(f"{base_routes}.{name}_routes")
            app.register_blueprint(getattr(controller_mod, f"{name}_bp"))
            app.register_blueprint(getattr(routes_mod, f"{name}_api_bp"))

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_GROUP_BREW_FATHER",
                "label": "Integração BrewFather",
                "parent_code": None,
                "route": None,
                "icon": "bi-cloud-arrow-down",
            },
            {
                "code": "TX_BREWFATHER_SYNCS",
                "label": "Sincronizações",
                "parent_code": "TX_GROUP_BREW_FATHER",
                "description": "Log de sincronizações com o BrewFather.",
                "icon": "bi-arrow-repeat",
                "route": "/brewstation/brewfather-syncs",
                "permission_required": "brewfather_syncs.list",
            },
        ]
