"""
addons/addon_brewstation/features/feature_device_manager/feature.py
"""
__module__ = "FeatureDeviceManager"

from core.feature_base import FeatureBase


class FeatureDeviceManager(FeatureBase):
    def register_models(self) -> list:
        from addons.addon_brewstation.features.feature_device_manager.model.device_function import DeviceFunction
        from addons.addon_brewstation.features.feature_device_manager.model.device_metadata import DeviceMetadata
        from addons.addon_brewstation.features.feature_device_manager.model.device_actor import DeviceActor
        from addons.addon_brewstation.features.feature_device_manager.model.emulated_device import EmulatedDevice

        return [DeviceFunction, DeviceMetadata, DeviceActor, EmulatedDevice]

    def register_routes(self, app) -> None:
        from addons.addon_brewstation.features.feature_device_manager.controller.device_functions import device_functions_bp
        from addons.addon_brewstation.features.feature_device_manager.api.routes.device_functions_routes import device_functions_api_bp
        from addons.addon_brewstation.features.feature_device_manager.controller.device_metadatas import device_metadatas_bp
        from addons.addon_brewstation.features.feature_device_manager.api.routes.device_metadatas_routes import device_metadatas_api_bp
        from addons.addon_brewstation.features.feature_device_manager.controller.device_actors import device_actors_bp
        from addons.addon_brewstation.features.feature_device_manager.api.routes.device_actors_routes import device_actors_api_bp
        from addons.addon_brewstation.features.feature_device_manager.controller.emulated_devices import emulated_devices_bp
        from addons.addon_brewstation.features.feature_device_manager.api.routes.emulated_devices_routes import emulated_devices_api_bp

        for bp in [
            device_functions_bp, device_functions_api_bp,
            device_metadatas_bp, device_metadatas_api_bp,
            device_actors_bp, device_actors_api_bp,
            emulated_devices_bp, emulated_devices_api_bp,
        ]:
            app.register_blueprint(bp)

    def get_transactions(self) -> list:
        return [
            {
                "code": "TX_DEVICE_MANAGER",
                "label": "Dispositivos IoT",
                "group": "BrewStation",
                "description": "Cadastro de dispositivos, funções e atores.",
                "icon": "bi-cpu-fill",
                "route": "/brewstation/device-metadatas",
                "permission_required": "device_metadatas.list",
            },
        ]
