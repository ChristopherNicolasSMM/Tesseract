"""
tests/test_phase5_module_manager.py

Cobre a lacuna encontrada ao migrar o primeiro Addon real: o prefixo
de tabela precisa ser aplicado no REGISTRO (boot do app), não só na
geração (CrudGen, Fase 4) — senão um boot normal (sem passar por
`generate`) reimporta o model com o nome curto, sem prefixo.

Também cobre a descoberta automática a partir de addon.json/addon.py
em disco (lacuna deixada aberta desde a Fase 1).
"""
import json
import shutil
import tempfile
from pathlib import Path

import pytest

from core.app_factory import create_app
from core.db import db
from core.addon_base import AddonBase
from core.feature_base import FeatureBase


# ── Addon + Feature de smoke-test (definidos uma única vez, nível de módulo) ─

class _SmoketestStrain(db.Model):
    __tablename__ = "modmgrtest_feature_item"  # nome deliberadamente diferente de
    id = db.Column(db.Integer, primary_key=True)  # "strain" — colidia com o YeastStrain
    name = db.Column(db.String(100))               # real (Fase 5), mesmo nome curto


class _SmoketestRecipe(db.Model):
    __tablename__ = "modmgrtest_addon_core_item"  # era "recipe" — colidia com MashRecipe real (Fase 6)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))


class _FeatureSmoke(FeatureBase):
    def register_models(self):
        return [_SmoketestStrain]


class _AddonSmoke(AddonBase):
    def register_routes(self, app):
        pass

    def register_models(self):
        return [_SmoketestRecipe]

    def get_features(self):
        return [
            _FeatureSmoke(
                {"name": "feature_smoke", "label": "Smoke", "version": "1.0.0",
                 "table_prefix_suffix": "smokefeat"},
                addon_table_prefix=self.table_prefix,
            )
        ]


@pytest.fixture
def app():
    app = create_app(env="testing")
    yield app


def test_register_module_aplica_prefixo_no_addon_e_na_feature(app):
    addon = _AddonSmoke({"name": "addonsmoke", "label": "Addon Smoke",
                          "version": "1.0.0", "table_prefix": "addonsmoke"})

    with app.app_context():
        app.module_manager.register_module(addon)

        assert _SmoketestRecipe.__tablename__ == "tesseract_addonsmoke_modmgrtest_addon_core_item"
        assert _SmoketestStrain.__tablename__ == "tesseract_addonsmoke_smokefeat_modmgrtest_feature_item"


class _SmoketestRecipeEvento(db.Model):
    __tablename__ = "recipe_evento"
    id = db.Column(db.Integer, primary_key=True)


class _AddonSmokeEvento(AddonBase):
    def register_routes(self, app):
        pass

    def register_models(self):
        return [_SmoketestRecipeEvento]


def test_register_module_dispara_evento_core_module_activated(app):
    from core.event_bus import event_bus

    recebido = {}

    def _listener(module_name, module_type):
        recebido["name"] = module_name
        recebido["type"] = module_type

    event_bus.subscribe("core.module.activated", _listener)

    addon = _AddonSmokeEvento({"name": "addonsmoke2", "label": "Addon Smoke 2",
                                "version": "1.0.0", "table_prefix": "addonsmoke2"})

    with app.app_context():
        app.module_manager.register_module(addon)

    assert recebido == {"name": "addonsmoke2", "type": "addon"}


# ── Descoberta a partir de disco ────────────────────────────────────────────

_tmp_dir = tempfile.mkdtemp(prefix="tesseract_discovery_test_")
_ADDONS_DIR = Path(_tmp_dir) / "addons"
_addon_dir = _ADDONS_DIR / "addon_discotest"
_addon_dir.mkdir(parents=True, exist_ok=True)

(_addon_dir / "addon.json").write_text(
    json.dumps({"name": "discotest", "label": "Disco Test", "version": "1.0.0",
                "table_prefix": "discotest"}),
    encoding="utf-8",
)

(_addon_dir / "addon.py").write_text(
    """
__module__ = "AddonDiscotest"

from core.addon_base import AddonBase


class _DiscoModel:
    pass


class AddonDiscotest(AddonBase):
    def register_routes(self, app):
        pass

    def register_models(self):
        return []
""",
    encoding="utf-8",
)


def _cleanup_discovery_tmp_dir():
    shutil.rmtree(_tmp_dir, ignore_errors=True)


def test_discover_and_register_addons_encontra_e_registra(app):
    with app.app_context():
        registrados = app.module_manager.discover_and_register_addons(_ADDONS_DIR)
        assert "discotest" in registrados
        assert "discotest" in app.module_manager.active_modules

    _cleanup_discovery_tmp_dir()


def test_discover_ignora_pasta_sem_addon_json(app, tmp_path):
    pasta_vazia = tmp_path / "addons"
    (pasta_vazia / "addon_incompleto").mkdir(parents=True)

    with app.app_context():
        registrados = app.module_manager.discover_and_register_addons(pasta_vazia)
        assert registrados == []


# ── create_all_pending_tables() vs. comando `flask db ...` (BACKLOG.md) ─────
#
# Achado real: db.create_all() rodando sempre no boot "ganhava a corrida"
# do Alembic sempre que uma migration nova criava uma tabela (ou
# adicionava uma coluna) — a tabela/coluna já existia (criada pelo
# create_all, que reflete o model já atualizado) quando a migration
# tentava criar/alterar, e o Alembic falhava com "already exists" /
# "duplicate column". Corrigido pulando db.create_all() quando o
# processo é um comando `flask db ...`.

def test_running_under_flask_db_command_detecta_subcomando_db(monkeypatch):
    from core.module_manager import _running_under_flask_db_command

    monkeypatch.setattr("sys.argv", ["run.py", "db", "upgrade"])
    assert _running_under_flask_db_command() is True

    monkeypatch.setattr("sys.argv", ["flask", "db", "stamp", "head"])
    assert _running_under_flask_db_command() is True


def test_running_under_flask_db_command_false_para_outros_comandos(monkeypatch):
    from core.module_manager import _running_under_flask_db_command

    monkeypatch.setattr("sys.argv", ["run.py", "start"])
    assert _running_under_flask_db_command() is False

    monkeypatch.setattr("sys.argv", ["pytest"])
    assert _running_under_flask_db_command() is False

    monkeypatch.setattr("sys.argv", ["run.py"])
    assert _running_under_flask_db_command() is False


def test_create_all_pending_tables_pula_create_all_sob_comando_db(app, monkeypatch):
    from unittest.mock import patch

    with app.app_context():
        monkeypatch.setattr("sys.argv", ["run.py", "db", "upgrade"])
        with patch("core.module_manager.db.create_all") as mocked_create_all:
            app.module_manager.create_all_pending_tables()
            mocked_create_all.assert_not_called()


def test_create_all_pending_tables_roda_normalmente_fora_de_comando_db(app, monkeypatch):
    from unittest.mock import patch

    with app.app_context():
        monkeypatch.setattr("sys.argv", ["run.py", "start"])
        with patch("core.module_manager.db.create_all") as mocked_create_all:
            app.module_manager.create_all_pending_tables()
            mocked_create_all.assert_called_once()
