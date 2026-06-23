"""
addons/addon_brewstation/features/feature_yeast_bank/feature.py
"""
__module__ = "FeatureYeastBank"

from core.feature_base import FeatureBase


class FeatureYeastBank(FeatureBase):
    def register_models(self) -> list:
        from addons.addon_brewstation.features.feature_yeast_bank.model.yeast_strain import YeastStrain
        return [YeastStrain]

    def register_routes(self, app) -> None:
        from addons.addon_brewstation.features.feature_yeast_bank.controller.yeast_strains import yeast_strains_bp
        from addons.addon_brewstation.features.feature_yeast_bank.api.routes.yeast_strains_routes import yeast_strains_api_bp

        app.register_blueprint(yeast_strains_bp)
        app.register_blueprint(yeast_strains_api_bp)
