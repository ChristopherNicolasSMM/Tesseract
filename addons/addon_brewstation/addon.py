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
        from core.feature_base import FeatureBase
        from addons.addon_brewstation.features.feature_yeast_bank.feature import FeatureYeastBank

        feature_manifest = self.manifest.get("features", [{}])[0]
        # feature.json é a fonte completa — addon.json só tem o resumo
        import json
        from pathlib import Path
        feature_json_path = (
            Path(__file__).parent / "features" / "feature_yeast_bank" / "feature.json"
        )
        full_manifest = json.loads(feature_json_path.read_text(encoding="utf-8"))

        return [FeatureYeastBank(full_manifest, addon_table_prefix=self.table_prefix)]
