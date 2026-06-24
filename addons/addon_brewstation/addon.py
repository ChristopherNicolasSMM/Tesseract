"""
addons/addon_brewstation/addon.py
"""
__module__ = "AddonBrewstation"

from core.addon_base import AddonBase


class AddonBrewstation(AddonBase):
    def register_routes(self, app) -> None:
        pass  # núcleo do addon ainda não tem rota própria (sem model em root/ ainda)

    def register_models(self) -> list:
        return []  # núcleo do addon ainda não tem model próprio nesta fase

    def get_features(self) -> list:
        import json
        from pathlib import Path

        from addons.addon_brewstation.features.feature_yeast_bank.feature import FeatureYeastBank
        from addons.addon_brewstation.features.feature_device_manager.feature import FeatureDeviceManager
        from addons.addon_brewstation.features.feature_mash_control.feature import FeatureMashControl

        base = Path(__file__).parent / "features"

        yeast_bank_manifest = json.loads(
            (base / "feature_yeast_bank" / "feature.json").read_text(encoding="utf-8")
        )
        device_manager_manifest = json.loads(
            (base / "feature_device_manager" / "feature.json").read_text(encoding="utf-8")
        )
        mash_control_manifest = json.loads(
            (base / "feature_mash_control" / "feature.json").read_text(encoding="utf-8")
        )

        return [
            FeatureYeastBank(yeast_bank_manifest, addon_table_prefix=self.table_prefix),
            FeatureDeviceManager(device_manager_manifest, addon_table_prefix=self.table_prefix),
            FeatureMashControl(mash_control_manifest, addon_table_prefix=self.table_prefix),
        ]
