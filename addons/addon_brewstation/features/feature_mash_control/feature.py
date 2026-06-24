"""
addons/addon_brewstation/features/feature_mash_control/feature.py
"""
__module__ = "FeatureMashControl"

from core.feature_base import FeatureBase


class FeatureMashControl(FeatureBase):
    def register_models(self) -> list:
        from addons.addon_brewstation.features.feature_mash_control.model.mash_recipe import MashRecipe
        from addons.addon_brewstation.features.feature_mash_control.model.brew_plant import BrewPlant
        from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_vessel import BrewPlantVessel
        from addons.addon_brewstation.features.feature_mash_control.model.brew_plant_mapping import BrewPlantMapping
        from addons.addon_brewstation.features.feature_mash_control.model.brew_session import BrewSession
        from addons.addon_brewstation.features.feature_mash_control.model.brew_session_step import BrewSessionStep
        from addons.addon_brewstation.features.feature_mash_control.model.brew_session_log import BrewSessionLog
        from addons.addon_brewstation.features.feature_mash_control.model.brew_session_alarm import BrewSessionAlarm
        from addons.addon_brewstation.features.feature_mash_control.model.dashboard_layout import DashboardLayout
        from addons.addon_brewstation.features.feature_mash_control.model.dashboard_widget import DashboardWidget
        from addons.addon_brewstation.features.feature_mash_control.model.automation_rule import AutomationRule
        from addons.addon_brewstation.features.feature_mash_control.model.automation_rule_log import AutomationRuleLog

        return [
            MashRecipe, BrewPlant, BrewPlantVessel, BrewPlantMapping,
            BrewSession, BrewSessionStep, BrewSessionLog, BrewSessionAlarm,
            DashboardLayout, DashboardWidget, AutomationRule, AutomationRuleLog,
        ]

    def register_routes(self, app) -> None:
        names = [
            "mash_recipes", "brew_plants", "brew_plant_vessels", "brew_plant_mappings",
            "brew_sessions", "brew_session_steps", "brew_session_logs", "brew_session_alarms",
            "dashboard_layouts", "dashboard_widgets", "automation_rules", "automation_rule_logs",
        ]
        base_controller = "addons.addon_brewstation.features.feature_mash_control.controller"
        base_routes = "addons.addon_brewstation.features.feature_mash_control.api.routes"

        import importlib
        for name in names:
            controller_mod = importlib.import_module(f"{base_controller}.{name}")
            routes_mod = importlib.import_module(f"{base_routes}.{name}_routes")
            app.register_blueprint(getattr(controller_mod, f"{name}_bp"))
            app.register_blueprint(getattr(routes_mod, f"{name}_api_bp"))

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_MASH_RECIPES",
                "label": "Receitas de Brassagem",
                "group": "BrewStation",
                "description": "Cadastro de receitas.",
                "icon": "bi-journal-text",
                "route": "/brewstation/mash-recipes",
                "permission_required": "mash_recipes.list",
            },
            {
                "code": "TX_BREW_SESSIONS",
                "label": "Sessões de Brassagem",
                "group": "BrewStation",
                "description": "Acompanhamento de sessões em andamento e finalizadas.",
                "icon": "bi-thermometer-half",
                "route": "/brewstation/brew-sessions",
                "permission_required": "brew_sessions.list",
            },
        ]
