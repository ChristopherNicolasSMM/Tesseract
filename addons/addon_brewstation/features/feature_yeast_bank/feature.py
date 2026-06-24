"""
addons/addon_brewstation/features/feature_yeast_bank/feature.py
"""
__module__ = "FeatureYeastBank"

from core.feature_base import FeatureBase


class FeatureYeastBank(FeatureBase):
    def register_models(self) -> list:
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_storage_device import YeastStorageDevice
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_storage_reading import YeastStorageReading
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_item import YeastBankItem
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_starter_log import YeastStarterLog
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_cell_count_history import YeastCellCountHistory
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_event import YeastBankEvent
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_bank_config import YeastBankConfig

        # Ordem importa só para leitura humana aqui — a aplicação do
        # prefixo e a criação de tabela toleram qualquer ordem (skill 02,
        # FK resolvida lazy pelo SQLAlchemy; testado na conversa de
        # arquitetura). Mantida na ordem de dependência por clareza.
        return [
            YeastStrain,
            YeastStorageDevice,
            YeastStorageReading,
            YeastBankItem,
            YeastStarterLog,
            YeastCellCountHistory,
            YeastBankEvent,
            YeastBankConfig,
        ]

    def register_routes(self, app) -> None:
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_strains import yeast_strains_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_strains_routes import yeast_strains_api_bp
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_storage_devices import yeast_storage_devices_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_storage_devices_routes import yeast_storage_devices_api_bp
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_storage_readings import yeast_storage_readings_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_storage_readings_routes import yeast_storage_readings_api_bp
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_bank_items import yeast_bank_items_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_bank_items_routes import yeast_bank_items_api_bp
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_starter_logs import yeast_starter_logs_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_starter_logs_routes import yeast_starter_logs_api_bp
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_cell_count_histories import yeast_cell_count_histories_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_cell_count_histories_routes import yeast_cell_count_histories_api_bp
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_bank_events import yeast_bank_events_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_bank_events_routes import yeast_bank_events_api_bp
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_bank_configs import yeast_bank_configs_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_bank_configs_routes import yeast_bank_configs_api_bp

        for bp in [
            yeast_strains_bp, yeast_strains_api_bp,
            yeast_storage_devices_bp, yeast_storage_devices_api_bp,
            yeast_storage_readings_bp, yeast_storage_readings_api_bp,
            yeast_bank_items_bp, yeast_bank_items_api_bp,
            yeast_starter_logs_bp, yeast_starter_logs_api_bp,
            yeast_cell_count_histories_bp, yeast_cell_count_histories_api_bp,
            yeast_bank_events_bp, yeast_bank_events_api_bp,
            yeast_bank_configs_bp, yeast_bank_configs_api_bp,
        ]:
            app.register_blueprint(bp)

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_YEAST_BANK",
                "label": "Banco de Levedura",
                "group": "BrewStation",
                "description": "Cadastro e acompanhamento de cepas de levedura.",
                "icon": "bi-droplet-fill",
                "route": "/brewstation/yeast-strains",
                "permission_required": "yeast_strains.list",
            },
        ]

