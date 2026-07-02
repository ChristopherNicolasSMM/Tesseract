"""
addons/addon_device_manager/addon.py

Addon promovido de Feature (addon_brewstation/features/feature_device_manager)
para Addon independente — ver docs/skills/05-proposta-addon-device-manager-e-mqtt.md
para o histórico completo da decisão e das FKs removidas na promoção.
"""
__module__ = "AddonDeviceManager"

from core.addon_base import AddonBase


class AddonDeviceManager(AddonBase):
    def register_models(self) -> list:
        from addons.addon_device_manager.root.model.device_function import DeviceFunction
        from addons.addon_device_manager.root.model.device_metadata import DeviceMetadata
        from addons.addon_device_manager.root.model.device_actor import DeviceActor
        from addons.addon_device_manager.root.model.emulated_device import EmulatedDevice

        return [DeviceFunction, DeviceMetadata, DeviceActor, EmulatedDevice]

    def register_routes(self, app) -> None:
        from addons.addon_device_manager.root.controller.device_functions import device_functions_bp
        from addons.addon_device_manager.root.api.routes.device_functions_routes import device_functions_api_bp
        from addons.addon_device_manager.root.controller.device_metadatas import device_metadatas_bp
        from addons.addon_device_manager.root.api.routes.device_metadatas_routes import device_metadatas_api_bp
        from addons.addon_device_manager.root.controller.device_actors import device_actors_bp
        from addons.addon_device_manager.root.api.routes.device_actors_routes import device_actors_api_bp
        from addons.addon_device_manager.root.controller.emulated_devices import emulated_devices_bp
        from addons.addon_device_manager.root.api.routes.emulated_devices_routes import emulated_devices_api_bp

        for bp in [
            device_functions_bp, device_functions_api_bp,
            device_metadatas_bp, device_metadatas_api_bp,
            device_actors_bp, device_actors_api_bp,
            emulated_devices_bp, emulated_devices_api_bp,
        ]:
            app.register_blueprint(bp)

        # Registro em memória (TASK_REGISTRY) — não grava nada no banco
        # aqui (tabelas de task ainda não existem neste ponto do boot,
        # ver core/module_manager.py: register_routes roda antes de
        # create_all_pending_tables). A ScheduledTask real (com
        # schedule/aprovação) é criada pelo operador via UI do monitor
        # (/admin/tasks), escolhendo este target.
        from core.task_registry import register_task
        from addons.addon_device_manager.root.services import mqtt_client_service
        register_task("device_manager.mqtt_reconnect", lambda: mqtt_client_service.reconnect(app))

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_GROUP_DEVICE_MANAGER",
                "label": "Dispositivos IoT",
                "parent_code": None,
                "route": None,
                "icon": "bi-cpu-fill",
            },
            {
                "code": "TX_DEVICE_FUNCTIONS",
                "label": "Funções de Dispositivo",
                "parent_code": "TX_GROUP_DEVICE_MANAGER",
                "description": "Tipos de leitura/ação — sensor, atuador, híbrido.",
                "icon": "bi-funnel",
                "route": "/device-manager/device-functions",
                "permission_required": "device_functions.list",
            },
            {
                "code": "TX_DEVICE_MANAGER",
                "label": "Dispositivos",
                "parent_code": "TX_GROUP_DEVICE_MANAGER",
                "description": "Cadastro dos equipamentos físicos.",
                "icon": "bi-cpu-fill",
                "route": "/device-manager/device-metadatas",
                "permission_required": "device_metadatas.list",
            },
            {
                "code": "TX_DEVICE_ACTORS",
                "label": "Atores",
                "parent_code": "TX_GROUP_DEVICE_MANAGER",
                "description": "Liga uma porta de um dispositivo a uma Função.",
                "icon": "bi-plug-fill",
                "route": "/device-manager/device-actors",
                "permission_required": "device_actors.list",
            },
            {
                "code": "TX_EMULATED_DEVICES",
                "label": "Dispositivos Emulados",
                "parent_code": "TX_GROUP_DEVICE_MANAGER",
                "description": "Simula leituras sem hardware real.",
                "icon": "bi-magic",
                "route": "/device-manager/emulated-devices",
                "permission_required": "emulated_devices.list",
            },
        ]
