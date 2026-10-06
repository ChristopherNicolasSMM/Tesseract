"""Traduções de features registradas precisam chegar ao modal Core e ao Jinja."""
from types import SimpleNamespace
import json
import sys
from flask import Flask
from services.core import i18n_service


def test_i18n_merge_features_registradas_sem_carregar_diretorios_inativos(tmp_path, monkeypatch):
    addon_dir = tmp_path / "addon"
    feature_dir = addon_dir / "features" / "registered"
    inactive_dir = addon_dir / "features" / "inactive"
    for directory, data in ((addon_dir, {"shared": "addon"}),
                            (feature_dir, {"shared": "feature", "feature.confirm": "Confirmar conversão?"}),
                            (inactive_dir, {"inactive.only": "Não carregar"})):
        (directory / "i18n").mkdir(parents=True)
        (directory / "i18n" / "pt_BR.json").write_text(json.dumps(data), encoding="utf-8")
    class Addon: pass
    class Feature: pass
    Addon.__module__ = "test_registered_addon"
    Feature.__module__ = "test_registered_feature"
    monkeypatch.setitem(sys.modules, Addon.__module__, SimpleNamespace(__file__=str(addon_dir / "addon.py")))
    monkeypatch.setitem(sys.modules, Feature.__module__, SimpleNamespace(__file__=str(feature_dir / "feature.py")))
    app = Flask(__name__)
    app.module_manager = SimpleNamespace(active_modules={"addon": Addon()}, active_features={"addon/registered": Feature()})
    i18n_service.reset_cache()
    try:
        with app.app_context():
            translations = i18n_service.all_translations()
            assert translations["shared"] == "feature"
            assert i18n_service.translate("feature.confirm") == "Confirmar conversão?"
            assert "inactive.only" not in translations
    finally:
        i18n_service.reset_cache()
