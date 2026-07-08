"""
addons/addon_device_manager/addon.py

Addon promovido de Feature (addon_brewstation/features/feature_device_manager)
para Addon independente — ver docs/skills/05-proposta-addon-device-manager-e-mqtt.md
para o histórico completo da decisão e das FKs removidas na promoção.
"""
__module__ = "AddonDeviceManager"

from core.addon_base import AddonBase


class AddonDeviceManager(AddonBase):
    # register_models() migrado pro caminho de auto-descoberta (skill
    # 09) nesta sessão — o default de AddonBase cobre os 4 models de
    # root/model/ (conferido 1:1 antes da migração).

    def register_routes(self, app) -> None:
        # Blueprints via auto-descoberta (skill 09). O que NÃO é
        # mecânico (registro do target de reconexão MQTT no
        # TASK_REGISTRY em memória) continua explícito abaixo.
        from core.module_discovery import own_base_package, discover_blueprints

        info = own_base_package(self)
        if info:
            base_package, _ = info
            for blueprint in discover_blueprints(base_package):
                app.register_blueprint(blueprint)

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
