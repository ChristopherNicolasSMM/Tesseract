"""
addons/addon_brewstation/features/feature_mash_control/feature.py
"""
__module__ = "FeatureMashControl"

from core.feature_base import FeatureBase


class FeatureMashControl(FeatureBase):
    # register_models() migrado pro caminho de auto-descoberta (skill
    # 09) nesta sessão — o default de FeatureBase cobre os 18 models
    # de model/ (conferido 1:1 antes da migração).

    def register_routes(self, app) -> None:
        # Blueprints via auto-descoberta (skill 09) — cobre os 18
        # pares controller/api.routes já mecânicos que estavam
        # listados à mão aqui. O que NÃO é mecânico (inscrição no
        # EventBus do motor de automação) continua explícito abaixo,
        # não faz parte do default de nenhuma auto-descoberta.
        from core.module_discovery import own_base_package, discover_blueprints

        info = own_base_package(self)
        if info:
            base_package, _ = info
            for blueprint in discover_blueprints(base_package):
                app.register_blueprint(blueprint)

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
                "code": "TX_GROUP_MASH_CONTROL",
                "label": "Controle de Mostura",
                "parent_code": "TX_GROUP_BREWSTATION",  # skill 10 secao 7.1 - agrupa sob o Addon pai
                "route": None,
                "icon": "bi-thermometer-half",
            },
            {
                "code": "TX_MASH_RECIPES",
                "label": "Receitas de Brassagem",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Cadastro de receitas.",
                "icon": "bi-journal-text",
                "route": "/brewstation/mash-recipes",
                "permission_required": "mash_recipes.list",
            },
            {
                "code": "TX_BREW_PLANTS",
                "label": "Plantas de Brassagem",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Estrutura física — panelas, fermentadores.",
                "icon": "bi-diagram-3",
                "route": "/brewstation/brew-plants",
                "permission_required": "brew_plants.list",
            },
            {
                "code": "TX_BREW_PLANT_VESSELS",
                "label": "Vasilhames",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Vasilhames de uma planta de brassagem.",
                "icon": "bi-cup-straw",
                "route": "/brewstation/brew-plant-vessels",
                "permission_required": "brew_plant_vessels.list",
            },
            {
                "code": "TX_BREW_PLANT_MAPPINGS",
                "label": "Mapeamentos de Planta",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Liga um vasilhame a um sensor/atuador do device_manager.",
                "icon": "bi-bezier2",
                "route": "/brewstation/brew-plant-mappings",
                "permission_required": "brew_plant_mappings.list",
            },
            {
                "code": "TX_BREW_SESSIONS",
                "label": "Sessões de Brassagem",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Acompanhamento de sessões em andamento e finalizadas.",
                "icon": "bi-thermometer-half",
                "route": "/brewstation/brew-sessions",
                "permission_required": "brew_sessions.list",
            },
            {
                "code": "TX_BREW_SESSION_STEPS",
                "label": "Passos da Sessão",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Etapas registradas de uma sessão de brassagem.",
                "icon": "bi-list-ol",
                "route": "/brewstation/brew-session-steps",
                "permission_required": "brew_session_steps.list",
            },
            {
                "code": "TX_BREW_SESSION_LOGS",
                "label": "Logs da Sessão",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Registro livre de eventos de uma sessão.",
                "icon": "bi-card-text",
                "route": "/brewstation/brew-session-logs",
                "permission_required": "brew_session_logs.list",
            },
            {
                "code": "TX_BREW_SESSION_ALARMS",
                "label": "Alarmes da Sessão",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Alarmes disparados durante uma sessão.",
                "icon": "bi-bell-fill",
                "route": "/brewstation/brew-session-alarms",
                "permission_required": "brew_session_alarms.list",
            },
            {
                "code": "TX_DASHBOARD_LAYOUTS",
                "label": "Layouts de Dashboard",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Layouts visuais de acompanhamento (em construção).",
                "icon": "bi-grid-1x2",
                "route": "/brewstation/dashboard-layouts",
                "permission_required": "dashboard_layouts.list",
            },
            {
                "code": "TX_DASHBOARD_WIDGETS",
                "label": "Widgets de Dashboard",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Widgets de um layout de dashboard.",
                "icon": "bi-pip",
                "route": "/brewstation/dashboard-widgets",
                "permission_required": "dashboard_widgets.list",
            },
            {
                "code": "TX_AUTOMATION_RULES",
                "label": "Regras de Automação",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Definição de regras sensor->ação (sem motor de execução ainda).",
                "icon": "bi-cpu",
                "route": "/brewstation/automation-rules",
                "permission_required": "automation_rules.list",
            },
            {
                "code": "TX_AUTOMATION_RULE_LOGS",
                "label": "Histórico de Regras",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Histórico de avaliação de regras de automação.",
                "icon": "bi-clock-history",
                "route": "/brewstation/automation-rule-logs",
                "permission_required": "automation_rule_logs.list",
            },
            {
                "code": "TX_RECIPE_INGREDIENTS",
                "label": "Ingredientes de Receita",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Ingredientes normalizados de uma receita, resolvidos contra o estoque.",
                "icon": "bi-basket",
                "route": "/brewstation/recipe-ingredients",
                "permission_required": "recipe_ingredients.list",
            },
            {
                "code": "TX_INGREDIENT_MAPPINGS",
                "label": "Mapeamento de Ingredientes (De-Para)",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Cache de resolução: descrição de origem -> Material do estoque.",
                "icon": "bi-arrow-left-right",
                "route": "/brewstation/ingredient-mappings",
                "permission_required": "ingredient_mappings.list",
            },
            {
                "code": "TX_RECIPE_HISTORYS",
                "label": "Histórico de Receitas",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Snapshot de cada versão salva de uma receita.",
                "icon": "bi-hourglass-split",
                "route": "/brewstation/recipe-historys",
                "permission_required": "recipe_historys.list",
            },
            {
                "code": "TX_MASH_STEPS",
                "label": "Passos de Mostura",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Rampas de temperatura de mostura planejadas na receita.",
                "icon": "bi-thermometer-half",
                "route": "/brewstation/mash-steps",
                "permission_required": "mash_steps.list",
            },
            {
                "code": "TX_FERMENTATION_STEPS",
                "label": "Etapas de Fermentação",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Perfil de fermentação planejado na receita.",
                "icon": "bi-droplet-half",
                "route": "/brewstation/fermentation-steps",
                "permission_required": "fermentation_steps.list",
            },
            {
                "code": "TX_WATER_PROFILES",
                "label": "Perfis de Água",
                "parent_code": "TX_GROUP_MASH_CONTROL",
                "description": "Perfil de água da receita (íons/pH por contexto).",
                "icon": "bi-droplet",
                "route": "/brewstation/water-profiles",
                "permission_required": "water_profiles.list",
            },
        ]
