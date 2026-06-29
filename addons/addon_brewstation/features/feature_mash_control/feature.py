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

        # Motor de automação reativo (Fase E, Opção 1) — inscreve-se
        # uma única vez no EventBus do Core (core/event_bus.py,
        # evento "device_manager.actor.value_changed"). Registro em
        # memória, sem acesso a banco (idêntico em espírito ao
        # core.task_registry.register_task() do addon_device_manager).
        from addons.addon_brewstation.features.feature_mash_control.services import automation_engine
        automation_engine.register()

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_MASH_RECIPES",
                "label": "Receitas de Brassagem",
                "group": "Controle de Mostura",
                "description": "Cadastro de receitas.",
                "icon": "bi-journal-text",
                "route": "/brewstation/mash-recipes",
                "permission_required": "mash_recipes.list",
            },
            {
                "code": "TX_BREW_PLANTS",
                "label": "Plantas de Brassagem",
                "group": "Controle de Mostura",
                "description": "Estrutura física — panelas, fermentadores.",
                "icon": "bi-diagram-3",
                "route": "/brewstation/brew-plants",
                "permission_required": "brew_plants.list",
            },
            {
                "code": "TX_BREW_PLANT_VESSELS",
                "label": "Vasilhames",
                "group": "Controle de Mostura",
                "description": "Vasilhames de uma planta de brassagem.",
                "icon": "bi-cup-straw",
                "route": "/brewstation/brew-plant-vessels",
                "permission_required": "brew_plant_vessels.list",
            },
            {
                "code": "TX_BREW_PLANT_MAPPINGS",
                "label": "Mapeamentos de Planta",
                "group": "Controle de Mostura",
                "description": "Liga um vasilhame a um sensor/atuador do device_manager.",
                "icon": "bi-bezier2",
                "route": "/brewstation/brew-plant-mappings",
                "permission_required": "brew_plant_mappings.list",
            },
            {
                "code": "TX_BREW_SESSIONS",
                "label": "Sessões de Brassagem",
                "group": "Controle de Mostura",
                "description": "Acompanhamento de sessões em andamento e finalizadas.",
                "icon": "bi-thermometer-half",
                "route": "/brewstation/brew-sessions",
                "permission_required": "brew_sessions.list",
            },
            {
                "code": "TX_BREW_SESSION_STEPS",
                "label": "Passos da Sessão",
                "group": "Controle de Mostura",
                "description": "Etapas registradas de uma sessão de brassagem.",
                "icon": "bi-list-ol",
                "route": "/brewstation/brew-session-steps",
                "permission_required": "brew_session_steps.list",
            },
            {
                "code": "TX_BREW_SESSION_LOGS",
                "label": "Logs da Sessão",
                "group": "Controle de Mostura",
                "description": "Registro livre de eventos de uma sessão.",
                "icon": "bi-card-text",
                "route": "/brewstation/brew-session-logs",
                "permission_required": "brew_session_logs.list",
            },
            {
                "code": "TX_BREW_SESSION_ALARMS",
                "label": "Alarmes da Sessão",
                "group": "Controle de Mostura",
                "description": "Alarmes disparados durante uma sessão.",
                "icon": "bi-bell-fill",
                "route": "/brewstation/brew-session-alarms",
                "permission_required": "brew_session_alarms.list",
            },
            {
                "code": "TX_DASHBOARD_LAYOUTS",
                "label": "Layouts de Dashboard",
                "group": "Controle de Mostura",
                "description": "Layouts visuais de acompanhamento (em construção).",
                "icon": "bi-grid-1x2",
                "route": "/brewstation/dashboard-layouts",
                "permission_required": "dashboard_layouts.list",
            },
            {
                "code": "TX_DASHBOARD_WIDGETS",
                "label": "Widgets de Dashboard",
                "group": "Controle de Mostura",
                "description": "Widgets de um layout de dashboard.",
                "icon": "bi-pip",
                "route": "/brewstation/dashboard-widgets",
                "permission_required": "dashboard_widgets.list",
            },
            {
                "code": "TX_AUTOMATION_RULES",
                "label": "Regras de Automação",
                "group": "Controle de Mostura",
                "description": "Definição de regras sensor->ação (sem motor de execução ainda).",
                "icon": "bi-cpu",
                "route": "/brewstation/automation-rules",
                "permission_required": "automation_rules.list",
            },
            {
                "code": "TX_AUTOMATION_RULE_LOGS",
                "label": "Histórico de Regras",
                "group": "Controle de Mostura",
                "description": "Histórico de avaliação de regras de automação.",
                "icon": "bi-clock-history",
                "route": "/brewstation/automation-rule-logs",
                "permission_required": "automation_rule_logs.list",
            },
        ]
