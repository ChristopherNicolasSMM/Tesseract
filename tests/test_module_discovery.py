"""
tests/test_module_discovery.py

Cobre a skill 09 (auto-descoberta): rotas/models/menu descobertos via
pkgutil, escopados por módulo, sem nenhum registro manual em
addon.py/feature.py.

Diferente de test_phase4_crudgen.py (que usa um project_root externo
via tempfile), este teste precisa de um Addon real DENTRO de addons/
— a auto-descoberta usa importlib.import_module com caminho pontuado
real (addons.addon_X...), então só funciona se existir de fato na
árvore importável do projeto. Criado e removido em torno da suíte
deste arquivo (fixture de módulo); nunca fica no working tree fora da
execução dos testes.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from core.app_factory import create_app
from core.db import db

_ADDONS_DIR = Path(__file__).resolve().parent.parent / "addons"
_ADDON_NAME = "autodisco_smoketest"
_ADDON_DIR = _ADDONS_DIR / f"addon_{_ADDON_NAME}"


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _scaffold_addon() -> None:
    _write(_ADDON_DIR / "__init__.py")
    _write(_ADDON_DIR / "addon.json", json.dumps({
        "name": _ADDON_NAME,
        "label": "Autodisco Smoketest",
        "version": "1.0.0",
        "type": "addon",
        "table_prefix": "autodisco",
        "requires": [],
        "features": [],
        "default_locale": "pt_BR",
    }))
    # Nenhum override de register_models/register_routes/get_transactions
    # — o ponto do teste é justamente confirmar que o default (skill 09)
    # sozinho já é suficiente.
    _write(_ADDON_DIR / "addon.py", (
        '__module__ = "AddonAutodiscoSmoketest"\n'
        "from core.addon_base import AddonBase\n\n\n"
        "class AddonAutodiscoSmoketest(AddonBase):\n"
        "    pass\n"
    ))

    _write(_ADDON_DIR / "model" / "__init__.py")
    _write(_ADDON_DIR / "model" / "widget.py", (
        "from core.db import db\n"
        "from annotations import label, plural, menu_icon\n\n\n"
        '@label("Widget de Teste")\n'
        '@plural("autodisco_widgets")\n'
        '@menu_icon("bi-star")\n'
        "class AutodiscoWidget(db.Model):\n"
        '    __tablename__ = "widget"\n'
        "    id = db.Column(db.Integer, primary_key=True)\n"
        "    name = db.Column(db.String(100), nullable=False)\n"
        "    is_deleted = db.Column(db.Boolean, default=False, nullable=False)\n"
        "    deleted_at = db.Column(db.DateTime, nullable=True)\n"
    ))

    _write(_ADDON_DIR / "controller" / "__init__.py")
    _write(_ADDON_DIR / "controller" / "widgets.py", (
        "from flask import Blueprint, jsonify\n\n\n"
        'autodisco_widgets_bp = Blueprint("autodisco_widgets", __name__, url_prefix="/autodisco/widgets")\n\n\n'
        '@autodisco_widgets_bp.route("/", endpoint="list")\n'
        "def list_widgets():\n"
        "    return jsonify([])\n"
    ))

    _write(_ADDON_DIR / "i18n" / "pt_BR.json", "{}")


def _cleanup_addon() -> None:
    shutil.rmtree(_ADDON_DIR, ignore_errors=True)
    for modname in list(sys.modules):
        if (
            modname.startswith(f"addons.addon_{_ADDON_NAME}")
            or modname.startswith(f"_tesseract_dynamic_addon_{_ADDON_NAME}")
        ):
            del sys.modules[modname]


@pytest.fixture(scope="module")
def app():
    _scaffold_addon()
    try:
        flask_app = create_app(env="testing")
        yield flask_app
    finally:
        _cleanup_addon()


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


def test_rota_descoberta_e_registrada_automaticamente(client):
    resp = client.get("/autodisco/widgets/")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_model_descoberto_e_tabela_criada_com_prefixo_correto(app):
    with app.app_context():
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        assert "tesseract_autodisco_widget" in inspector.get_table_names()


def test_permissao_camada1_seedada_para_model_auto_descoberto(app):
    with app.app_context():
        from model.core.permission import Permission
        assert Permission.query.filter_by(name="autodisco_widgets.list").first() is not None


def test_transacao_auto_gerada_com_convencao_da_skill09(app):
    with app.app_context():
        from model.core.transaction import Transaction
        tx = Transaction.query.filter_by(code="TX_AUTO_AUTODISCO_WIDGETS").first()
        assert tx is not None
        assert tx.label == "Widget de Teste"
        assert tx.icon == "bi-star"
        assert tx.parent is not None
        assert tx.parent.label == "Autodisco Smoketest"  # label do módulo dono (skill 00, adenda)
        assert tx.parent.code == "TX_GROUP_AUTO_AUTODISCO_SMOKETEST"  # skill 10, namespace separado do manual
        assert tx.permission_required == "autodisco_widgets.list"
        assert tx.route == "/autodisco/widgets/"


def test_addon_com_override_manual_continua_funcionando(app):
    """
    Não-regressão: addon_brewstation e addon_device_manager sobrescrevem
    os 3 métodos manualmente — o boot completo (fixture `app`, que já
    descobre TODOS os addons reais também) não deve quebrar nem duplicar
    nada por causa do default novo.
    """
    with app.app_context():
        from model.core.transaction import Transaction
        # Nenhuma Transação TX_AUTO_* deveria ter sido gerada para models
        # de addons que já declaram get_transactions() manualmente.
        # Nota: comparação em Python, não SQL LIKE — "_" é wildcard de
        # 1 caractere em LIKE, e colidiria com códigos manuais reais
        # tipo "TX_AUTOMATION_RULES" (automation_rules do device_manager).
        auto_codes = {t.code for t in Transaction.query.all() if t.code.startswith("TX_AUTO_")}
        assert auto_codes == {"TX_AUTO_AUTODISCO_WIDGETS"}
